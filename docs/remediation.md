# Cleanup plans and generated scripts

CloudZombie never runs remediation. It builds a plan from a stored finding and may generate a Bash artifact for a human to review and execute separately.

## Cleanup plan

A cleanup plan contains:

- Finding, resource, detector, account, and region identifiers.
- Plain-language detector and observation summary.
- Structured evidence.
- Resource and observation timestamps, counts, streak, persistence threshold, and days remaining.
- Known dependencies.
- CloudFormation and Terraform ownership status.
- Estimated amount, confidence, source, explanation, and upper-bound flag.
- Detection confidence and remediation risk.
- Preconditions, warnings, limitations, and recommended action.
- Script kind, availability, and unavailable reason.

Plans keep resource age separate from condition-observation age.

## Eligibility

A guarded remediation script is offered only when the finding:

- Is open.
- Comes from the unattached-EBS or unassociated-EIP detector.
- Has remediation risk LOW.

Every other finding receives a read-only investigation script. `ScriptUnavailableReason` values and current human text are:

| Reason | Text |
|---|---|
| `newly_observed` | The condition is newly observed and has not met the persistence threshold. |
| `remediation_risk_review` | The finding requires human review before any remediation. |
| `remediation_risk_high` | The finding has high remediation risk. |
| `cloudformation_owned` | The resource is owned by CloudFormation; change the stack instead. |
| `blocking_dependency` | A known dependency blocks remediation. |
| `finding_not_open` | The finding is not open. |
| `detector_has_no_destructive_script` | This detector has no destructive script. |

Reason selection checks status first, then detector support, confirmed ownership, blocking dependencies, newly observed persistence, and risk.

## Guarded EBS script anatomy

The checked golden example is `backend/tests/golden/ebs_delete.sh`.

1. **Header**: generator, kind, detector, UTC timestamp, scan ID, expected account, region, and resource.
2. **Readonly block**: validated `EXPECTED_ACCOUNT_ID`, `REGION`, `VOLUME_ID`, ignore tag key/value, and the CloudFormation tag key.
3. **Strict mode**: `set -euo pipefail`.
4. **`abort()`**: prints `ABORTED`, a reason, and `No action performed.`, then exits non-zero.
5. **`verify_account()`**: calls STS with an explicit region and requires the current account to equal the validated expected account.
6. **`verify_volume_state()`**: re-fetches the volume, requires `available`, and requires zero attachments.
7. **`verify_volume_tags()`**: aborts when the current ignore tag matches case-insensitively or when `aws:cloudformation:stack-name` is present.
8. **`show_current_volume()`**: displays live AWS CLI output. No stored title, description, tag, or evidence text is copied into the script.
9. **`offer_snapshot()`**: optionally creates and waits for a pre-deletion snapshot. The script warns that the snapshot incurs charges.
10. **`confirm_deletion()`**: requires the exact phrase `DELETE <volume-id>`.
11. **Delete**: runs the single `delete-volume` command only after every check passes.

## Elastic IP differences

The guarded EIP script:

- Re-fetches `AssociationId`, `InstanceId`, and `NetworkInterfaceId`.
- Aborts if any association now exists.
- Performs the same account, ignore-tag, and CloudFormation-tag checks.
- Warns that the public address may not be recoverable.
- Requires the exact phrase `RELEASE <allocation-id>` before `release-address`.

## Investigation scripts

Investigation scripts use describe-only commands and do not include ignore-tag assignments that would be unused.

- EBS investigation describes the volume and account-owned snapshots from it.
- EIP investigation describes the address.
- EC2 investigation describes the instance, attached volumes, and associated addresses. It contains no termination command.
- Snapshot investigation describes the snapshot, sharing, AMI references, and lock status. `delete-snapshot` appears only as a comment or echoed commented command.

## Bulk scripts

Bulk generation includes only guarded-eligible findings from one account. Ineligible and cross-account findings are returned in a skipped list before generation.

At runtime each resource is processed independently:

- Live state and tags are rechecked.
- An invalid or changed resource is marked `SKIPPED` and processing continues.
- Every included resource needs its own exact confirmation.
- The final summary reports completed and skipped counts.

Bulk mode does not offer pre-deletion snapshots.

## Deliberately absent

- No EC2 termination command is generated.
- Snapshot deletion remains disabled in executable code.
- The application has no endpoint that executes a script.
- No free-form finding metadata is interpolated.

## Running a script safely

1. Download the script from the finding page or raw API endpoint.
2. Read the complete file and compare account, region, resource, checks, and warnings with the cleanup plan.
3. Configure the AWS CLI for the same account shown in the header.
4. Run it separately:

```bash
bash cloudzombie-delete-volume-vol-0a1b2c3d4e5f60001-eu-central-1.sh
```

5. Read every live-state table and prompt before confirming.

`ABORTED` means the script failed closed and performed no destructive action for that target. Investigate the printed reason rather than bypassing it.

## Runtime-metadata rule

Tags, names, titles, descriptions, evidence, ownership notes, and other free text may originate in AWS or user input. They are safe for database/UI display, but they never enter executable generation.

`ScriptService` validates and forwards only machine identifiers from stored fields and configured safe tag identifiers. The generator API accepts `ValidatedIdentifier` objects, re-runs validators after composition, checks readonly assignment syntax, and rejects non-ASCII or non-printable output. Static Bash templates reference variables populated only from those validated values.

This boundary is covered by hostile-metadata injection tests, golden files, shellcheck, behavioural fake-AWS tests, and the destructive-call audit described in [security-model.md](security-model.md).
