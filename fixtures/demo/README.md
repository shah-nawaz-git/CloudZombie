# Demo dataset

`dataset.json` is deterministic input for `DemoProvider`. Each resource lists the timeline steps in which it exists. Resource timestamps are calculated from a persisted demo anchor and `created_days_ago`; findings and observations are produced by the real detector, pricing, ownership, classification, and reconciliation code.

Account: `123456789012`.

## Resources

| Resource | Steps | Purpose |
|---|---:|---|
| `vol-0a1b2c3d4e5f60001`, gp3 500 GiB, eu-central-1 | 1–5 | Persistent LOW-risk hero finding |
| `vol-0a1b2c3d4e5f60002`, gp2 100 GiB | 1–5 | Confirmed `customer-api-prod` CloudFormation resource; HIGH risk |
| `vol-0a1b2c3d4e5f60003`, gp3 200 GiB, 6,000 IOPS, 500 MiB/s | 4–5 | Newly observed and exercises gp3 performance pricing |
| `vol-0a1b2c3d4e5f60004`, ignore tags | 1–5 | Ignored finding with reason `DR staging` |
| `vol-0a1b2c3d4e5f60009`, gp2 20 GiB | 1–2 | Resolves when absent under complete coverage at step 3 |
| `eipalloc-0a1b2c3d4e5f60001` | 1–5 | Persistent unassociated address |
| `eipalloc-0a1b2c3d4e5f60002` | 3–5 | Later unassociated address |
| `eipalloc-0a1b2c3d4e5f60003` | 1–5 | Associated with stopped instance 0001; residual cost, not an EIP finding |
| `eipalloc-0a1b2c3d4e5f60004` | 1–5 | Associated with running instance 0003; not a finding |
| `i-0a1b2c3d4e5f60001`, stopped t3.large | 1–5 | Two attached volumes and one public address |
| `i-0a1b2c3d4e5f60002`, stopped t3.small | 1–5 | Root volume, hostile Name tag as plain data, and retained-resource CloudFormation tags producing LIKELY ownership |
| `i-0a1b2c3d4e5f60003`, running | 1–5 | Not a finding |
| `snap-0a1b2c3d4e5f60001`, standard 200 GiB | 1–5 | Valid deleted-source review |
| `snap-0a1b2c3d4e5f60002` | 1–5 | Deleted source and registered AMI dependency; HIGH risk |
| `snap-0a1b2c3d4e5f60003`, archive 500 GiB | 1–5 | Shared with account `210987654321`; HIGH risk |
| `snap-0a1b2c3d4e5f60004` | 1–5 | Existing source volume; not a finding |
| `snap-0a1b2c3d4e5f60005` | 1–5 | AWS placeholder `vol-ffffffff`; deliberately skipped |
| `ap-southeast-2` | all | `list_snapshots` access-denied fault, producing partial coverage |
| `me-south-1` | all | Not opted in, producing skipped coverage |

Attached volumes `vol-0a1b2c3d4e5f61001`, `...1002`, and `...1003` provide stopped-instance evidence and pricing without becoming unattached-volume findings.

The deleted-source fixture IDs use valid 17-hex forms:

- `vol-0deadbeef00000001`
- `vol-0deadbeef00000002`
- `vol-0deadbeef00000003`

## Seeded timeline

`DemoSeeder` runs:

| Step | Scan time |
|---:|---|
| 1 | anchor −21 days |
| 2 | anchor −14 days |
| 3 | anchor −7 days |
| 4 | anchor −2 days |

A user scan uses step 5 at the anchor.

## Expected evaluation after step 4

- Open EBS findings: volumes 0001, 0002, and 0003.
- Ignored: volume 0004.
- Resolved: volume 0009, with two lifetime observations.
- Open unassociated Elastic IP findings: addresses 0001 and 0002.
- Stopped-instance findings: instances 0001 and 0002.
- Snapshot findings: snapshots 0001, 0002, and 0003.
- Volume 0002 ownership is CONFIRMED and risk HIGH.
- Instance 0002 ownership is LIKELY and risk REVIEW.
- Snapshot 0002 has a registered-AMI blocker; snapshot 0003 has a sharing blocker.
- Hero volume 0001 is persistent with four observations and LOW risk.
- Volume 0003 remains newly observed after step 4.
- `ap-southeast-2` is partial; `me-south-1` is skipped.
- Total finding rows: 12.

`backend/tests/test_demo_evaluation.py` asserts these results and the step-5 continuation.
