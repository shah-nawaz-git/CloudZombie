# CloudZombie architecture

This document is the design authority for the codebase. If code and this document
disagree, one of them is wrong and must be fixed; do not let them drift silently.

CloudZombie is a self-hosted AWS **cleanup planner**. It discovers resources that
deserve review through a strictly read-only AWS boundary, tracks the suspicious
condition across repeated scans, checks known dependencies and CloudFormation
ownership, estimates public-list-price exposure, and generates guarded Bash
remediation scripts that revalidate live AWS state before any destructive step.
CloudZombie's own runtime never mutates AWS.

## 1. Layering

```
frontend (Next.js)  ──HTTP──▶  app/api (FastAPI routers, Pydantic schemas)
                                  │
                                  ▼
                              app/services      ScanService, FindingService, PlanService,
                                  │             ScriptService, SettingsService, DemoSeeder
              ┌───────────────────┼───────────────────────────┐
              ▼                   ▼                           ▼
        app/scanner          app/persistence            app/remediation
   (orchestration,        (SQLAlchemy models,        (validators, plan builder,
    coverage, history      repositories)               script templates/generator)
    reconciliation)
              │
   ┌──────────┼─────────────┬──────────────┬──────────────┐
   ▼          ▼             ▼              ▼              ▼
detectors  dependencies  ownership      pricing       app/providers
 (pure)     (pure)      (uses provider) (uses provider  ├─ base.py      CloudProvider ABC + domain records
                                         ReadOnlyPricing) ├─ demo.py      DemoProvider (fixtures, no credentials)
                                                         └─ aws/
                                                            ├─ guard.py     botocore operation allowlist guard
                                                            ├─ readonly.py  ReadOnlyEc2 / ReadOnlySts / ReadOnlyPricing / ReadOnlyCloudFormation
                                                            └─ provider.py  AwsProvider (only place that touches boto3 clients)
```

Rules that the layering enforces:

* Only `app/providers/aws/` imports `boto3`/`botocore` clients. A test asserts this with a
  static import scan of the whole `app` package (allow-list: `app/providers/aws/**`
  and `app/core/aws_errors.py` for exception classes).
* Detectors, dependency checks, ownership, pricing, services, API routes and the CLI
  only receive a `CloudProvider` (or an even narrower object) — never a client.
* Detectors never price, never write to the database, never render scripts.
* Only `app/remediation/scripts/` produces executable text, and only from validated
  identifiers (section 10).

## 2. Domain vocabulary

| Enum | Values | Meaning |
|---|---|---|
| `Mode` | `demo`, `live` | Which provider backs the application |
| `ResourceType` | `ebs_volume`, `elastic_ip`, `ec2_instance`, `ebs_snapshot` | |
| `DetectorType` | `unattached_ebs_volume`, `unassociated_elastic_ip`, `stopped_ec2_instance`, `snapshot_missing_source_volume` | One detector per resource-analysis scenario |
| `FindingStatus` | `open`, `dismissed`, `resolved`, `ignored` | See §6 |
| `PersistenceState` | `newly_observed`, `persistent` | Derived from observation history + thresholds |
| `DetectionConfidence` | `HIGH`, `MEDIUM`, `LOW` | How sure we are the detector condition is true |
| `RemediationRisk` | `LOW`, `REVIEW`, `HIGH` | How conservative remediation must be |
| `CostConfidence` | `HIGH`, `MEDIUM`, `LOW`, `UNAVAILABLE` | Trust in the cost estimate |
| `OwnershipStatus` | `CONFIRMED`, `LIKELY`, `UNKNOWN` | CloudFormation ownership; `UNKNOWN` ≠ unmanaged |
| `ScanStatus` | `running`, `completed`, `partial`, `failed` | |
| `RegionCoverageStatus` | `complete`, `partial`, `failed`, `skipped` | Per region |
| `DetectorCoverageStatus` | `complete`, `missing_permission`, `failed`, `skipped` | Per (region, detector) |
| `ScriptKind` | `guarded_remediation`, `investigation` | See §10 |

Terminology rules (enforced by review and by string tests on the API/UI):

* Never "orphaned snapshot" — say **snapshot with deleted source volume**.
* Never "unattached/stopped/unused for X days" derived from a creation timestamp.
  Say **Resource age**, **First observed &lt;condition&gt;**, **Observed in N scans**.
* Never "guaranteed savings" — say **estimated monthly list-price exposure** or
  **estimated monthly cleanup opportunity**.
* "Known dependencies", never "all dependencies".

## 3. Time semantics (mandatory)

Every timestamp is timezone-aware UTC. The ORM uses a `UtcDateTime` type decorator so
SQLite (tests) and PostgreSQL (production) behave identically.

| Field | Source | Meaning |
|---|---|---|
| `resource_created_at` | AWS (`CreateTime`, `LaunchTime`, `StartTime`) | When AWS created the resource. Context only. |
| `first_observed_at` | CloudZombie | First scan in which this finding's condition was observed. Never changes once set. |
| `last_observed_at` | CloudZombie | Most recent scan that observed the condition. |
| `observation_count` | CloudZombie | Total scans that observed the condition (lifetime). |
| `consecutive_observations` | CloudZombie | Length of the current uninterrupted streak; reset to 0 on resolve, restarts at 1 on reappearance. |
| `streak_started_at` | CloudZombie | `first_observed_at` of the current streak. Equals `first_observed_at` unless the finding resolved and reappeared. |
| `observation_age_days` | derived | `(last_observed_at - streak_started_at)` in whole days. A single observation has age 0. |

`persistence_state = persistent` iff
`observation_age_days >= thresholds[detector_type]` **and**
`consecutive_observations >= min_consecutive_observations` (default 2). Otherwise `newly_observed`.

Scan-level `observed_at` is `scan.started_at`; all observations recorded by one scan share it.

## 4. Persistence model

Primary keys are UUIDv4 (`sa.Uuid`). Money is `Numeric(12, 4)` → `Decimal`. Structured
data is `sa.JSON` (portable between SQLite and PostgreSQL). Alembic owns the schema for
PostgreSQL; tests may use `metadata.create_all` on SQLite, and one test runs the Alembic
migrations against SQLite to prove they are portable.

### `scans`
```
id, mode, account_id, principal_arn, seeded (bool, demo history only)
started_at, finished_at, status
requested_regions JSON[str], completed_regions, partial_regions, failed_regions, skipped_regions JSON[str]
coverage JSON  -> { region: { status, detectors: { detector_type: { status, error_code?, message?, missing_operation? } }, warnings: [str] } }
new_findings int, persistent_findings int, resolved_findings int, ignored_findings int
estimated_exposure Numeric  (sum of estimated_monthly_cost over OPEN findings observed by this scan with HIGH/MEDIUM cost confidence)
potential_exposure_low_confidence Numeric  (separate sum of LOW-confidence upper bounds over OPEN findings observed by this scan)
errors JSON[ { scope: "scan"|"region"|"detector", region?, detector_type?, code, message } ]
created_at
```

### `findings`
```
id
account_id, region, resource_type, resource_id, detector_type          UNIQUE together (finding identity)
title, summary
resource_created_at (nullable)
first_observed_at, last_observed_at, streak_started_at
observation_count, consecutive_observations
persistence_state
detection_confidence, remediation_risk, cost_confidence
estimated_monthly_cost (nullable Numeric), cost_explanation, pricing_source, pricing_timestamp (nullable)
cost_line_items JSON
evidence JSON            (detector-specific structured facts; may contain arbitrary AWS metadata; UI/DB only)
known_dependencies JSON  [ { kind, target_id?, description, blocks_remediation: bool } ]
ownership JSON           { status, stack_name?, stack_id?, logical_id?, source: "stack_resource_index"|"tags"|None, terraform: "UNKNOWN", notes: [str] }
related_resource_ids JSON [str]
status
resolved_at, dismissed_at, dismiss_reason, ignore_reason (all nullable)
first_scan_id, last_scan_id
created_at, updated_at
```

### `finding_observations`
One row per (finding, scan) in which the condition was observed.
```
id, finding_id, scan_id, observed_at
status_at_observation, persistence_state_at_observation, remediation_risk_at_observation
estimated_monthly_cost (nullable), evidence JSON
```

### `settings`
Single row (`id = 1`) holding `data JSON`, validated by the Pydantic `AppSettings` model:
```
regions: list[str] | None = None             # None → all accessible regions
thresholds_days: {unattached_ebs_volume: 7, unassociated_elastic_ip: 1, stopped_ec2_instance: 7, snapshot_missing_source_volume: 30}
min_consecutive_observations: 2
ignore_tag_key: "cloudzombie:ignore"        # validated against the safe tag charset (§10)
ignore_tag_value: "true"
ignore_reason_tag_key: "cloudzombie:reason"
pricing_mode: "auto" | "fallback_only" | "disabled"
pricing_cache_ttl_seconds: 86400
max_region_concurrency: 3
demo_anchor_at: datetime | None              # set by the demo seeder; DemoProvider computes resource ages from it
```

### `pricing_cache`
```
cache_key (PK), payload JSON, fetched_at, source
```

## 5. Provider boundary

### 5.1 Domain records (`app/providers/base.py`)
Frozen dataclasses; plain Python types only (no boto3 dicts leak upward):

```
Identity(account_id, principal_arn, identity_type: "role"|"user"|"assumed-role"|"root"|"unknown", user_id)
RegionInfo(name, opt_in_status: "opt-in-not-required"|"opted-in"|"not-opted-in")
Attachment(instance_id, device, state)
Volume(volume_id, state, volume_type, size_gib, iops, throughput_mibps, encrypted, created_at, snapshot_id, attachments: tuple[Attachment,...], tags: Mapping[str,str], availability_zone)
Address(allocation_id, public_ip, association_id, instance_id, network_interface_id, domain, tags)
BlockDevice(device_name, volume_id, status)
Instance(instance_id, state, instance_type, launched_at, block_devices, tags, platform)
Snapshot(snapshot_id, volume_id, owner_id, state, started_at, volume_size_gib, storage_tier, encrypted, description, tags)
Image(image_id, name, state, snapshot_ids: tuple[str,...], tags)
SnapshotAttributes(snapshot_id, shared_user_ids: tuple[str,...], shared_groups: tuple[str,...])
SnapshotLock(snapshot_id, lock_state: "compliance"|"governance"|"compliance-cooloff"|"expired"|None)
StackResource(region, stack_name, stack_id, logical_id, physical_id, resource_type, resource_status)
```

### 5.2 `CloudProvider` (ABC)
```python
class CloudProvider(ABC):
    mode: Mode
    def get_identity(self) -> Identity
    def list_regions(self) -> list[RegionInfo]
    def list_volumes(self, region: str) -> list[Volume]
    def list_addresses(self, region: str) -> list[Address]
    def list_instances(self, region: str) -> list[Instance]
    def list_snapshots(self, region: str) -> list[Snapshot]            # owner = self only
    def list_images(self, region: str) -> list[Image]                  # owner = self only
    def get_snapshot_attributes(self, region: str, snapshot_id: str) -> SnapshotAttributes
    def get_snapshot_locks(self, region: str, snapshot_ids: Sequence[str]) -> list[SnapshotLock]
    def list_stack_resources(self, region: str) -> list[StackResource] # all non-deleted stacks
    def get_prices(self, service_code: str, filters: Sequence[tuple[str, str]]) -> list[dict]  # raw price-list JSON documents; only PricingService calls this
```
Tags arrive inline on every EC2 record, so there is no separate `get_resource_tags`.
CloudFormation ownership is computed by `app/ownership` from `list_stack_resources`
plus tags, not by the provider.

Provider exceptions (`app/providers/errors.py`), all subclasses of `ProviderError`:
`ProviderCredentialsError`, `ProviderPermissionError(operation, region)`,
`ProviderRegionUnavailableError(region)`, `ProviderThrottledError`,
`ProviderTransientError`, `ProviderMalformedResponseError`.

### 5.3 Read-only wrappers (`app/providers/aws/readonly.py`)
Each wrapper holds its botocore client in a name-mangled private attribute and exposes
only the methods below. There is no generic `call`/`client`/`execute` escape hatch.

```
ReadOnlyEc2:            describe_regions, describe_volumes, describe_addresses, describe_instances,
                        describe_snapshots, describe_images, describe_snapshot_attribute, describe_locked_snapshots
ReadOnlySts:            get_caller_identity
ReadOnlyPricing:        get_products
ReadOnlyCloudFormation: list_stacks, list_stack_resources
```
Every list-style method paginates to exhaustion (botocore paginators where available;
manual `NextToken` loops otherwise) and translates `ClientError` into provider exceptions.

### 5.4 Operation guard (`app/providers/aws/guard.py`)
```python
ALLOWED_OPERATIONS: frozenset[str] = {
  "ec2:DescribeRegions", "ec2:DescribeVolumes", "ec2:DescribeAddresses", "ec2:DescribeInstances",
  "ec2:DescribeSnapshots", "ec2:DescribeImages", "ec2:DescribeSnapshotAttribute", "ec2:DescribeLockedSnapshots",
  "sts:GetCallerIdentity", "pricing:GetProducts",
  "cloudformation:ListStacks", "cloudformation:ListStackResources",
}
```
The `AwsProvider` creates one `botocore.session`/`boto3.Session` and registers a
`before-call.*.*` event handler that raises `OperationNotAllowedError` for any operation
outside the allowlist **before a request is signed or sent**. The same constant drives
`docs/iam-policy.json` (a test asserts exact set equality) and a test asserts that each
wrapper method maps to an allow-listed operation.

Retries: botocore `standard` retry mode, `max_attempts=6`, plus a wrapper-level
exponential backoff (base 0.5s, cap 8s, 4 attempts) for `Throttling`/`RequestLimitExceeded`.
Client construction: `AwsProvider` uses `boto3.Session(profile_name=settings.aws_profile)`
and otherwise the default credential chain; it never reads or stores secret material.

### 5.5 `DemoProvider` (`app/providers/demo.py`)
Loads `fixtures/demo/dataset.json`. Constructor: `DemoProvider(dataset, step: int, anchor: datetime)`.
Each fixture resource declares `steps: [int]` (which timeline steps it exists in) and
`created_days_ago: int`; `created_at = anchor - created_days_ago`. Fixture `faults` inject
permission/region errors per region and method for coverage demos. Requires no
credentials and no network.

## 6. Observation history and status reconciliation

`app/scanner/history.py::reconcile(session, scan, region, detector_type, candidates, coverage_status, settings, observed_at)`
is the only place that mutates finding rows during a scan. Rules:

1. If `coverage_status != complete` for `(region, detector_type)`: **do nothing** to existing
   findings in that cell. Missing permission must never look like "0 findings" and must never
   resolve findings.
2. For each candidate (identity = account_id + region + resource_type + resource_id + detector_type):
   * **No existing row** → insert with `first_observed_at = last_observed_at = streak_started_at = observed_at`,
     `observation_count = consecutive_observations = 1`, status `ignored` if `candidate.ignored` else `open`.
   * **Existing row, status in {open, ignored, dismissed}** → `last_observed_at = observed_at`,
     `observation_count += 1`, `consecutive_observations += 1`, refresh evidence/dependencies/ownership/pricing/
     `resource_created_at`. Status: `ignored` if candidate is ignored; `open` if previously ignored and tag removed;
     `dismissed` stays `dismissed`.
   * **Existing row, status `resolved`** (reappeared) → status `open` (or `ignored`), `last_observed_at = observed_at`,
     `observation_count += 1`, `consecutive_observations = 1`, `streak_started_at = observed_at`,
     `resolved_at = None`. **`first_observed_at` is never modified.**
   * Recompute `persistence_state`, `remediation_risk` (§7) and write one `finding_observations` row.
3. Existing rows in this cell with status in {open, ignored, dismissed} that were **not** in `candidates`
   → status `resolved`, `resolved_at = observed_at`, `consecutive_observations = 0`. Counts and
   `first_observed_at` are preserved.
4. Findings in regions not requested by this scan are untouched.

`dismissed` is user-set via the API (`open → dismissed`, `dismissed → open`). Users cannot set
`resolved` or `ignored`.

## 7. Classification rules

Detection confidence is `HIGH` for all four detectors: each condition is read directly
from authoritative AWS state (`State == available && no attachments`, `AssociationId is None`,
`State == stopped`, `VolumeId not in current volumes`).

Remediation risk (evaluated in `app/scanner/classification.py`):

```
base:
  unattached_ebs_volume         persistent → LOW, newly_observed → REVIEW
  unassociated_elastic_ip       persistent → LOW, newly_observed → REVIEW
  stopped_ec2_instance          REVIEW always
  snapshot_missing_source_volume REVIEW always
escalations (max wins):
  ownership.status == CONFIRMED                       → HIGH  (change the stack instead)
  ownership.status == LIKELY                          → at least REVIEW
  any known_dependency.blocks_remediation             → HIGH  (e.g. snapshot referenced by a registered AMI, shared snapshot, locked snapshot, AWS Backup-managed)
  status == ignored                                   → risk still computed, but no script is offered
```

Cost confidence is set by the pricing service: `HIGH` from the AWS Pricing API, `MEDIUM`
from the fallback table, `LOW` for snapshot upper bounds regardless of source,
`UNAVAILABLE` when nothing could be computed (finding still emitted).

Guarded destructive scripts (`ScriptKind.guarded_remediation`) are offered only when
`detector_type in {unattached_ebs_volume, unassociated_elastic_ip}` **and** `status == open`
**and** `remediation_risk == LOW`. Every other finding gets an `investigation` script
(read-only `aws ... describe-*` commands; snapshot scripts include a commented-out
`# aws ec2 delete-snapshot` line; EC2 scripts never mention `terminate-instances`).

## 8. Pricing

`app/pricing/service.py::PricingService.estimate(request: PricingRequest) -> PricingResult`.

```
PricingRequest = EbsVolumePricingRequest(region, volume_type, size_gib, iops, throughput_mibps)
               | ElasticIpPricingRequest(region)
               | SnapshotPricingRequest(region, size_gib, storage_tier)
               | StoppedInstancePricingRequest(region, volumes: [EbsVolumePricingRequest], public_ipv4_count)
PricingResult(estimated_monthly_cost: Decimal|None, cost_confidence, explanation: str,
              source: "aws_pricing_api"|"fallback_table"|"unavailable", pricing_timestamp, line_items: [ {label, quantity, unit, unit_price, monthly_cost} ], upper_bound: bool)
```

Backends, tried in order under `pricing_mode = auto`: `AwsPricingApiBackend` (through
`CloudProvider.get_prices`, `regionCode` filter, results cached in `pricing_cache` for the
TTL) then `FallbackTableBackend` (`app/pricing/fallback_prices.json`, public list prices with
a `captured_at` date and per-region entries; unknown regions use `us-east-1` prices and
the explanation says so). `fallback_only` skips the API (demo mode always uses this).
`disabled` yields `UNAVAILABLE`. Any exception in a backend degrades to the next one and
is recorded on the scan as a warning; detection never fails because of pricing.

Calculation rules:
* EBS gp3: `size × storage_price + max(iops-3000, 0) × iops_price + max(throughput-125, 0) × throughput_price`.
* io1/io2: `size × storage_price + iops × iops_price` (io2 tiered).
* gp2/st1/sc1/standard: `size × storage_price` (standard's per-I/O charge is noted as excluded).
* Elastic IP: `hourly_public_ipv4_price × 730`.
* Snapshot: `size × snapshot_tier_price`, marked `upper_bound = True`, confidence `LOW`, explanation states snapshots are incremental and exact reclaimable storage is unknown.
* Stopped instance: sum of attached-volume estimates + `public_ipv4_count × EIP monthly`; explanation states stopped compute is not billed and is not counted.

## 9. Scan orchestration (`app/scanner/engine.py`)

```
run_scan(requested_regions):
  identity = provider.get_identity()                     # failure → scan status failed, error recorded, nothing else runs
  scan = create scan row (running)
  regions = requested or settings.regions or [r.name for r in provider.list_regions() if r.opt_in_status != "not-opted-in"]
            (regions explicitly requested but reported not-opted-in are recorded as skipped)
  for region in regions (ThreadPoolExecutor, max_workers = settings.max_region_concurrency):
      ownership = OwnershipResolver(provider, region)      # lazily builds the stack-resource index once; permission failure → all UNKNOWN + region warning
      for detector in DETECTORS:
          try: candidates = detector.scan(provider, region, ScanContext(...))
               enrich: ownership.resolve(candidate) ; pricing.estimate(candidate.pricing_request)
               cell = complete
          except ProviderPermissionError as e:  cell = missing_permission (missing_operation = e.operation)
          except ProviderRegionUnavailableError: whole region = skipped; break
          except ProviderError as e:            cell = failed
  main thread: for each (region, detector) cell → reconcile(...)   # §6
  aggregate counts, exposure, coverage, region statuses, scan status:
      completed if every non-skipped region is complete, partial if any region is partial/failed, failed if identity failed or no region ran
```

Detector interface:
```python
class Detector(ABC):
    detector_type: DetectorType
    resource_type: ResourceType
    required_operations: frozenset[str]        # surfaced in coverage messages
    def scan(self, provider: CloudProvider, region: str, context: ScanContext) -> list[FindingCandidate]
```
`FindingCandidate` carries: identity fields, `title`, `summary`, `resource_created_at`,
`evidence`, `known_dependencies`, `related_resource_ids`, `tags`, `ignored`, `ignore_reason`,
`pricing_request`, `detection_confidence`. Ownership and pricing are filled in by the engine.

## 10. Remediation and the script-generation boundary

### 10.1 Cleanup plan (`app/remediation/plan.py`)
A `CleanupPlan` is a Pydantic model built from a stored finding + settings:
`finding_id, resource_id, resource_type, detector_type, account_id, region, plain_language_summary,
reason, evidence, observation_history {resource_created_at, first_observed_at, last_observed_at,
observation_count, consecutive_observations, streak_started_at, persistence_state, threshold_days},
known_dependencies, ownership, estimated_cost {amount, confidence, explanation, source, upper_bound},
detection_confidence, remediation_risk, preconditions[], warnings[], limitations[], recommended_action,
script_available: bool, script_kind, script_unavailable_reason`.

### 10.2 Identifier validators (`app/remediation/validators.py`)
Strict regexes; anything else raises `InvalidIdentifierError`:
```
account_id     ^\d{12}$
region         ^[a-z]{2,4}(-[a-z]{2,12}){1,3}-\d$          (+ optional allow-list check against discovered regions)
volume_id      ^vol-[0-9a-f]{8}(?:[0-9a-f]{9})?$
instance_id    ^i-[0-9a-f]{8}(?:[0-9a-f]{9})?$
snapshot_id    ^snap-[0-9a-f]{8}(?:[0-9a-f]{9})?$
allocation_id  ^eipalloc-[0-9a-f]{8}(?:[0-9a-f]{9})?$
scan_id        UUID
tag_key/value  ^[A-Za-z0-9_.:/+@-]{1,128}$ / {1,256}     (safe subset used for the ignore-tag setting)
timestamp      generated by us, formatted ISO-8601 basic, never user input
```

### 10.3 Script generator (`app/remediation/scripts/`)
Templates are static Bash text constants. The generator emits a header of
`readonly NAME="<validated value>"` assignments and then appends the static body which
references only those variables. **The generator API accepts typed, validated identifiers
only** — it never receives the finding's evidence, tags, title, description or any free text.
A final assertion re-validates every interpolated value and fails closed.

Every `guarded_remediation` script:
1. `set -euo pipefail`, `aws` CLI presence check, `--region "$REGION"` on every command.
2. `aws sts get-caller-identity` → abort on account mismatch (prints expected vs current).
3. Fetch the live resource; abort if missing; abort if the detector condition no longer holds
   (`State != available` or attachments ≠ 0; `AssociationId`/`InstanceId`/`NetworkInterfaceId` present).
4. Read current tags from AWS; abort if `IGNORE_TAG_KEY == IGNORE_TAG_VALUE`; abort if
   `aws:cloudformation:stack-name` is present (resource became stack-managed).
5. Print the live resource as an AWS CLI table (runtime lookup — no stored metadata copied).
6. Static warnings (EIP: release may be irrecoverable; EBS: optional snapshot-first prompt).
7. `read -r` confirmation that must equal `DELETE <resource-id>` / `RELEASE <allocation-id>` exactly.
8. The single destructive command, then a success line. Any abort prints `ABORTED`, a reason,
   and `No action performed.`

Bulk scripts (`POST /api/scripts/bulk`) reuse the same static functions with one
`(region, resource_id)` pair per eligible finding, each confirmed individually; ineligible
findings are returned in `skipped[]` with reasons and never appear in the script.

## 11. API surface

```
GET    /api/health                    {status, mode, database, version}
GET    /api/identity                  {mode, account_id, principal_arn, identity_type, verified_at, error}
POST   /api/scans                     {regions?: [str], wait?: bool} → 202 Scan (409 if a scan is running)
GET    /api/scans?limit=
GET    /api/scans/{id}
GET    /api/findings                  filters: resource_type, region, status, detection_confidence, remediation_risk,
                                      cost_confidence, ownership, persistence_state, first_observed_before/after,
                                      min_observation_count, q; sort: estimated_monthly_cost|resource_created_at|first_observed_at|
                                      observation_count|detection_confidence|remediation_risk; order; page, page_size
GET    /api/findings/{id}             finding + observations[]
PATCH  /api/findings/{id}             {status: "dismissed"|"open", reason?}
GET    /api/findings/{id}/plan        CleanupPlan
GET    /api/findings/{id}/script      {kind, filename, content, checks[], warnings[]}  (?format=raw → text/x-shellscript)
POST   /api/scripts/bulk              {finding_ids: [uuid]} → {content, included[], skipped[{finding_id, reason}]}
GET    /api/history                   per-scan series: started_at, open, new, resolved, exposure, exposure_by_resource_type
GET    /api/coverage                  latest scan coverage matrix
GET    /api/overview                  headline numbers for the Overview page
GET    /api/settings  PATCH /api/settings
```

## 12. Demo mode

`CLOUDZOMBIE_MODE=demo` wires `DemoProvider`, `pricing_mode=fallback_only`, and runs
`DemoSeeder` at startup when the database has no scans. The seeder fixes
`demo_anchor_at = now`, then runs the real scan engine four times with a frozen clock at
`anchor − 21d, −14d, −7d, −2d` using `DemoProvider(step=1..4)`. Seeded scans have
`seeded = true` and the UI labels them "seeded demo history". A user-triggered scan uses
`step = 5` (current state). Nothing in the history is hand-written: counts, first-observed
timestamps and resolutions all come from the engine.

Fixture contents (`fixtures/demo/dataset.json`, account `123456789012`):

| Resource | Steps | Purpose |
|---|---|---|
| `vol-0a1b2c3d4e5f60001` gp3 500 GiB, eu-central-1, created 180 d ago | 1–5 | Hero finding → persistent, LOW risk, guarded script |
| `vol-0a1b2c3d4e5f60002` gp2 100 GiB, tagged `aws:cloudformation:*`, in stack `customer-api-prod` | 1–5 | CloudFormation `CONFIRMED` → HIGH risk |
| `vol-0a1b2c3d4e5f60003` gp3 200 GiB, 6000 IOPS, 500 MiB/s, us-east-1 | 4–5 | Newly observed → REVIEW; exercises IOPS/throughput pricing |
| `vol-0a1b2c3d4e5f60004` gp3 50 GiB, `cloudzombie:ignore=true`, `cloudzombie:reason=DR staging` | 1–5 | Ignored |
| `vol-0a1b2c3d4e5f60009` gp2 20 GiB | 1–2 | Resolves at step 3 |
| `eipalloc-0a1b2c3d4e5f60001` eu-central-1 | 1–5 | Persistent EIP → LOW |
| `eipalloc-0a1b2c3d4e5f60002` us-east-1 | 3–5 | Persistent EIP |
| `eipalloc-0a1b2c3d4e5f60003` associated to stopped `i-…0001` | 1–5 | Counted in EC2 residual cost, not an EIP finding |
| `eipalloc-0a1b2c3d4e5f60004` associated to running `i-…0003` | 1–5 | Not a finding |
| `i-0a1b2c3d4e5f60001` stopped t3.large, 2 attached volumes + EIP | 1–5 | Stopped EC2 residual review |
| `i-0a1b2c3d4e5f60002` stopped, root volume only, hostile Name tag `$(rm -rf /)` | 1–5 | Stopped EC2; proves metadata never reaches scripts |
| `i-0a1b2c3d4e5f60003` running | 1–5 | Not a finding |
| `snap-0a1b2c3d4e5f60001` 200 GiB standard, source deleted | 1–5 | Snapshot review, REVIEW |
| `snap-0a1b2c3d4e5f60002` source deleted, referenced by `ami-0a1b2c3d4e5f60001` | 1–5 | Known dependency blocks → HIGH |
| `snap-0a1b2c3d4e5f60003` archive tier, shared with `210987654321` | 1–5 | Shared → HIGH |
| `snap-0a1b2c3d4e5f60004` source `vol-…0001` exists | 1–5 | Not a finding |
| `snap-0a1b2c3d4e5f60005` `VolumeId = vol-ffffffff` | 1–5 | Placeholder source id → not a finding, explained in docs |
| Region `ap-southeast-2` | | `list_snapshots` fault → `missing_permission` (partial coverage demo) |
| Region `me-south-1` | | `not-opted-in` → skipped |

Expected evaluation after seeding (step 4 completed): 3 open EBS findings, 2 open EIP findings,
2 stopped-EC2 findings, 3 snapshot findings, 1 ignored finding, 1 CloudFormation-confirmed
finding, 1 resolved finding. A test asserts exactly this.

## 13. Configuration

Environment (`app/core/config.py`, pydantic-settings, prefix-less names kept for familiarity):
```
CLOUDZOMBIE_MODE=demo|live            default demo
DATABASE_URL                          default sqlite:///./cloudzombie.db (dev); compose sets postgresql+psycopg://…
AWS_PROFILE                           optional; passed to boto3.Session(profile_name=…)
AWS_REGION_SELECTION                  optional comma list; seeds settings.regions on first start
PRICING_CACHE_TTL                     seconds, default 86400
CLOUDZOMBIE_CORS_ORIGINS              comma list, default http://localhost:3000
CLOUDZOMBIE_DEMO_SEED                 true|false, default true
CLOUDZOMBIE_LOG_LEVEL                 default INFO
```
Credentials are never read by application code; boto3 resolves them. Nothing secret is
logged, persisted, or returned by the API.

## 14. Testing strategy

* Backend: pytest, SQLite by default (`TEST_DATABASE_URL` overrides to PostgreSQL in CI),
  moto for EC2/STS/CloudFormation pagination and permission tests, botocore `Stubber` for
  Pricing and for error injection moto cannot model, `shellcheck-py` to lint every generated
  script, golden files under `backend/tests/golden/`.
* Frontend: Vitest + Testing Library for components/pages with mocked API; Playwright for
  the end-to-end demo flow against Docker Compose (CI) or local dev servers.
* Static safety tests: import scan for boto3 usage outside the provider package; reflection
  over wrapper classes vs `ALLOWED_OPERATIONS`; IAM policy equality; runtime grep-style test
  that no `app/` module (outside `remediation/scripts` templates) contains mutating AWS verbs.
