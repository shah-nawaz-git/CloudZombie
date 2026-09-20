# CloudZombie

Cloud cost tools can tell you that a resource may be costing money. CloudZombie focuses on the next step: showing why a resource deserves review and generating guarded cleanup instructions without giving the application write access to your AWS account.

CloudZombie is a self-hosted AWS cleanup planner. It discovers four resource conditions, records its own observation history, checks known dependencies and CloudFormation ownership, estimates monthly public list-price exposure, and generates scripts for a human to inspect and run separately.

## Problem

A resource being old or billable does not prove that it is safe to remove. AWS creation timestamps do not say when a volume became unattached, when an address became unassociated, or when a snapshot stopped being useful. Cost data also does not capture business intent, ownership, recovery requirements, or every dependency.

CloudZombie keeps those concerns separate: current condition, observation history, known dependencies, ownership evidence, cost estimate, remediation risk, and the final human decision.

## What CloudZombie does

- Discovers unattached EBS volumes, unassociated Elastic IPs, stopped EC2 instances, and snapshots with deleted source volumes.
- Reconciles findings across scans without treating missing permission as absence.
- Reports resource age separately from the age of CloudZombie's observation streak.
- Checks registered dependency types and CloudFormation ownership evidence.
- Estimates monthly public list-price exposure through the AWS Pricing API or a deterministic fallback table.
- Produces cleanup plans and guarded Bash scripts containing validated identifiers only.
- Runs in deterministic demo mode without AWS credentials.

## What CloudZombie does not do

- It does not expose a remediation API or call mutating AWS APIs.
- It does not prove that a resource is unnecessary.
- It does not discover every possible dependency.
- It does not infer Terraform ownership.
- It does not calculate a customer's final bill or guaranteed savings.
- It does not execute generated scripts.

## Screenshots / demo

![Overview](docs/screenshots/overview.png)
_Overview totals, scan controls, trends, and coverage._

![Findings](docs/screenshots/findings.png)
_Dense findings table with age, observation, cost, confidence, risk, ownership, and status._

![Finding detail](docs/screenshots/finding-detail.png)
_The finding detail page separates evidence, history, dependencies, ownership, cost, plan, and script._

![Scans](docs/screenshots/scans.png)
_Scan history and partial-coverage visibility._

### 60-second demo walkthrough

1. Open `http://localhost:3000`.
2. Point out the `DEMO MODE` indicator: no AWS credentials are required.
3. Select **Run scan** and wait for the new, persistent, and resolved counts.
4. Read the total **Estimated monthly cleanup opportunity** and the separate low-confidence snapshot exposure.
5. Open `vol-0a1b2c3d4e5f60001` from Findings.
6. Compare **Resource age: 180 days**, **First observed unattached: 21 days ago**, and **Observed unattached: N scans**. These are different facts.
7. Review `$47.60`, detection confidence `HIGH`, and remediation risk `LOW`.
8. Review Known dependencies and Infrastructure ownership.
9. Read the cleanup plan, preconditions, limitations, and recommended action.
10. Inspect the generated script: expected account, explicit region, validated volume ID, live `describe-volumes`, ignore-tag check, and exact confirmation phrase.

CloudZombie itself never has a remediation API; the generated script is a separate artifact for a human to review and run.

## Supported detectors

| Detector | Current condition | Detection confidence | Remediation risk | Script offered |
|---|---|---|---|---|
| Unattached EBS volume | `State == available` and no attachments | HIGH | REVIEW until persistent; LOW when persistent; ownership or blocking dependencies can raise it | Guarded deletion only when open and LOW; otherwise investigation |
| Unassociated Elastic IP | No association, instance, or network interface | HIGH | REVIEW until persistent; LOW when persistent; ownership or blocking dependencies can raise it | Guarded release only when open and LOW; otherwise investigation |
| Stopped EC2 instance | Instance state is `stopped` | HIGH | REVIEW, with normal ownership/dependency escalation | Read-only investigation only; no termination command |
| Snapshot with deleted source volume | Completed account-owned snapshot references a valid volume ID absent from the region | HIGH | REVIEW, raised to HIGH by blocking dependencies | Read-only investigation; deletion appears only as a commented command |

## Observation-history model

**Resource age is not time unused.** CloudZombie shows three separate facts:

1. Resource age from AWS metadata, where available.
2. First time CloudZombie observed the current detector condition.
3. Number of scans and consecutive scans that observed it.

See [docs/observation-model.md](docs/observation-model.md) for reconciliation and wording rules.

| Detector | Default persistence threshold |
|---|---:|
| Unattached EBS volume | 7 days |
| Unassociated Elastic IP | 1 day |
| Stopped EC2 instance | 7 days |
| Snapshot with deleted source volume | 30 days |

A finding also needs at least two consecutive observations by default.

## Safety architecture

```text
Next.js frontend -> FastAPI/services -> scanner/persistence/remediation
                                      -> detectors/dependencies/ownership/pricing
                                      -> CloudProvider
                                         |- DemoProvider
                                         `- AwsProvider -> restricted read-only wrappers
```

- `guard.py` rejects operations outside the exact allowlist before a request is sent.
- `ScanScopedProvider` memoizes read-only calls and provider errors for one scan.
- Application logic receives domain records, not raw boto3 clients.
- The script generator accepts validated account, region, resource, scan, and tag identifiers; it never receives finding titles, evidence, descriptions, or arbitrary tags.

See [docs/security-model.md](docs/security-model.md) and [docs/remediation.md](docs/remediation.md).

## Read-only AWS wrapper

| Wrapper | Exposed methods |
|---|---|
| `ReadOnlyEc2` | `describe_regions`, `describe_volumes`, `describe_addresses`, `describe_instances`, `describe_snapshots`, `describe_images`, `describe_snapshot_attribute`, `describe_locked_snapshots` |
| `ReadOnlySts` | `get_caller_identity` |
| `ReadOnlyPricing` | `get_products` |
| `ReadOnlyCloudFormation` | `list_stacks`, `list_stack_resources` |

Clients are name-mangled private attributes. There is no generic `client`, `call`, or `execute` escape hatch.

## IAM permissions

The policy is in [docs/iam-policy.json](docs/iam-policy.json). It allows exactly:

- `ec2:DescribeRegions`
- `ec2:DescribeVolumes`
- `ec2:DescribeAddresses`
- `ec2:DescribeInstances`
- `ec2:DescribeSnapshots`
- `ec2:DescribeImages`
- `ec2:DescribeSnapshotAttribute`
- `ec2:DescribeLockedSnapshots`
- `sts:GetCallerIdentity`
- `pricing:GetProducts`
- `cloudformation:ListStacks`
- `cloudformation:ListStackResources`

There is no CloudWatch permission and no `ec2:*` wildcard.

## Dependency checks

The registry currently contains nine kinds:

- `ebs_attachment`
- `eip_association`
- `attached_ebs_volume`
- `associated_elastic_ip`
- `registered_ami`
- `shared_snapshot`
- `public_snapshot`
- `snapshot_lock`
- `aws_backup_managed`

These are **Known dependencies, not all dependencies**. EC2 attached volumes and associated addresses are reported but do not block the instance investigation; the other registered checks block destructive remediation when present.

## CloudFormation ownership

- `CONFIRMED`: the resource's physical ID is present in the current stack-resource index. Change the stack rather than deleting manually.
- `LIKELY`: the resource carries `aws:cloudformation:*` tags but is absent from the index, such as a retained resource.
- `UNKNOWN`: no CloudFormation evidence was found, or CloudFormation could not be queried. UNKNOWN does not mean unmanaged.

Terraform remains `UNKNOWN`; CloudZombie does not guess Terraform ownership.

## Cost methodology

See [docs/pricing.md](docs/pricing.md).

CloudZombie reports **estimated monthly list-price exposure**, not savings. Pricing confidence is:

- HIGH: AWS Pricing API.
- MEDIUM: checked-in fallback table.
- LOW: snapshot upper bound, regardless of unit-price source.
- UNAVAILABLE: no estimate could be calculated.

The headline exposure includes open findings with HIGH or MEDIUM confidence. LOW-confidence snapshot upper bounds are shown separately.

## Snapshot limitations

EBS snapshots are incremental. AWS does not expose exact independently reclaimable blocks through the APIs used here. Snapshot size multiplied by a list price is an upper bound and deleting a snapshot may free much less storage than its apparent size. Snapshots may also support AMIs, sharing, backup plans, or locks.

## Demo mode

### Docker Compose

Docker was not available on the author's Windows development machine, so these commands are defined and covered by the CI Docker job but were not executed locally:

```bash
docker compose up --build
```

Then open `http://localhost:3000`.

### Without Docker

The helper scripts assume Bash:

```bash
scripts/dev-backend.sh
scripts/dev-frontend.sh
```

Equivalent explicit commands:

```bash
cd backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
CLOUDZOMBIE_MODE=demo DATABASE_URL=sqlite:///./cloudzombie.db ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

On Linux or macOS, use `./.venv/bin/python` instead. In another shell:

```bash
cd frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev
```

CLI scan:

```bash
cd backend
CLOUDZOMBIE_MODE=demo DATABASE_URL=sqlite:///./cloudzombie.db ./.venv/Scripts/python.exe -m app.cli scan
```

Demo mode seeds four scans at 21, 14, 7, and 2 days before its anchor by running the real scan engine. It does not hand-write findings.

## AWS mode

1. Attach the policy in [docs/iam-policy.json](docs/iam-policy.json) to the intended IAM principal.
2. Configure the standard boto3 credential chain, such as a profile:

```bash
export AWS_PROFILE=my-read-only-profile
docker compose -f docker-compose.yml -f docker-compose.live.yml up --build
```

The live override also passes through `AWS_REGION_SELECTION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN`, and mounts `${HOME}/.aws` read-only. The UI displays the verified account and principal ARN. Secret keys and session tokens are never persisted, logged, or returned.

Live mode has been exercised only against moto and botocore Stubber in this repository's tests. It has not been exercised against a live AWS account.

## Docker setup

Compose defines PostgreSQL, the FastAPI backend, and the standalone Next.js frontend with health checks and dependency ordering. The backend image runs as UID 1000, waits for the database, applies Alembic migrations, and starts Uvicorn. The frontend proxies same-origin `/api/*` requests to the backend.

Docker Compose has not been run on the author's Windows machine. The workflow is configured to build and exercise it in CI after the repository is pushed.

## Testing

Backend:

```bash
cd backend
./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m ruff format --check .
./.venv/Scripts/python.exe -m mypy app
./.venv/Scripts/python.exe -m pytest -q
```

Frontend:

```bash
cd frontend
npm run lint
npm run format:check
npx tsc --noEmit
npm run test
npm run build
```

End to end, with backend and frontend already running:

```bash
cd frontend
E2E_BASE_URL=http://localhost:3000 npx playwright test
```

The current verified counts are 236 backend pytest tests, 14 Vitest tests, and 1 Playwright specification. Recount them before relying on these figures.

The cross-platform aggregate script assumes Bash:

```bash
scripts/check-all.sh
```

## CI

`.github/workflows/ci.yml` defines:

- `backend`: PostgreSQL and SQLite tests, Ruff, formatting, mypy, coverage artifact.
- `frontend`: ESLint, Prettier check, TypeScript, Vitest, production build.
- `shellcheck`: golden scripts, backend entrypoint, and repository scripts.
- `docker`: Compose build/start, health/API checks, Playwright Chromium flow, logs on failure, cleanup.

CI configuration exists, but this documentation does not claim a successful remote CI run before the branch is pushed.

## Known limitations

- AWS only.
- One AWS account per deployment and scan.
- Four detectors.
- No automatic remediation.
- No comprehensive dependency graph.
- Terraform ownership remains unknown.
- AWS does not provide condition start time; CloudZombie uses its own observation history.
- Public list prices are not the final bill.
- Snapshot cleanup opportunity is inexact because snapshots are incremental.
- CloudZombie cannot determine business intent.
- Remediation requires human judgment.
- A read-only application architecture does not prove the configured IAM credentials lack write permission.
- Docker was not verified on the author's Windows machine; the Docker flow is configured for CI verification.
- Live AWS was not exercised; provider behavior is covered with moto and Stubber.

## Roadmap

The following items are not implemented:

- Terraform state integration.
- AWS Organizations and multi-account scanning.
- RDS, NAT Gateway, and S3 detectors.
- AWS Compute Optimizer import.
- CloudWatch utilization analysis.
- Scheduled scans and notifications.
- GCP support.
- Azure support.

## License

CloudZombie is licensed under the [MIT License](LICENSE).
