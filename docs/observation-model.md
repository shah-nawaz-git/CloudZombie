# Observation history model

**Resource age ≠ time unused.** CloudZombie does not derive the duration of an unattached, unassociated, stopped, or missing-source condition from an AWS creation timestamp.

## Fields

| Field | Source | Meaning |
|---|---|---|
| `resource_created_at` | AWS resource metadata | Context about the resource itself. It is not evidence of when the detector condition began. |
| `first_observed_at` | CloudZombie | First scan that observed this finding identity. It remains unchanged across resolution and reappearance. |
| `last_observed_at` | CloudZombie | Most recent scan that observed the condition. |
| `streak_started_at` | CloudZombie | First observation in the current uninterrupted streak. It changes when a resolved condition reappears. |
| `observation_count` | CloudZombie | Lifetime number of scans that observed the condition. |
| `consecutive_observations` | CloudZombie | Observations in the current uninterrupted streak; reset to zero on resolution and restarted at one. |
| `observation_age_days` | Derived | Whole days between `last_observed_at` and `streak_started_at`. A single observation has age zero. |
| `persistence_state` | Derived | `persistent` only when the age and consecutive-observation requirements are met; otherwise `newly_observed`. |

All persisted datetimes round-trip as timezone-aware UTC through `UtcDateTime`, including on SQLite.

## Reconciliation rules

Findings are reconciled by `(account, region, resource type, resource ID, detector type)`.

1. An incomplete detector cell does not change existing findings. Missing permission, provider failure, internal detector failure, and skipped coverage never mean that zero matching resources exist.
2. A first observation creates an open finding, or an ignored finding when the configured ignore tag matches. First, last, and streak timestamps are the scan start time; lifetime and consecutive counts start at one.
3. Re-observing an open, ignored, or dismissed finding updates the last timestamp, increments both counts, and refreshes evidence, dependencies, ownership, pricing, and resource metadata. A dismissed finding remains dismissed. Removing an ignore tag reopens an ignored finding.
4. Re-observing a resolved finding preserves the original first observation, clears resolution, restarts the streak and consecutive count, and opens or ignores it according to current tags.
5. When a complete cell no longer emits an existing open, ignored, or dismissed finding, that finding becomes resolved. Its first observation and lifetime count remain intact; consecutive observations become zero.
6. Findings in regions not requested by a scan are untouched.
7. Every positive observation writes a `finding_observations` row with status, persistence, risk, cost, cost confidence, and evidence as they were during that scan.

## Persistence thresholds

A finding is persistent when:

```text
observation_age_days >= detector threshold
and
consecutive_observations >= minimum consecutive observations
```

The default minimum is two.

| Detector | Default days |
|---|---:|
| Unattached EBS volume | 7 |
| Unassociated Elastic IP | 1 |
| Stopped EC2 instance | 7 |
| Snapshot with deleted source volume | 30 |

Thresholds affect persistence, not whether a current condition is detected.

## Why AWS timestamps are not used

- EBS `CreateTime` says when the volume was created, not when its last attachment ended.
- Snapshot `StartTime` says when snapshot creation started, not when the source volume disappeared or when the snapshot stopped being useful.
- EC2 `LaunchTime` is the latest start time after a stop/start cycle, not a reliable original creation time and not the beginning of the stopped condition.
- EC2 does not expose an Elastic IP allocation timestamp through the records used here.

CloudZombie therefore reports AWS timestamps only as resource context and separately records its own observations.

## Wording

Correct:

- `Resource age: 180 days`
- `First observed unattached: 21 days ago · 2026-08-30`
- `Observed unattached: 5 scans`
- `Current streak began on 2026-09-13`

Incorrect:

- `Unattached for 180 days` when 180 is volume age
- `Stopped for 60 days` derived from `LaunchTime`
- `Idle for N days` without condition history
- Any use of an "orphan" label for snapshots

## Partial coverage

A missing permission never resolves findings. For example, if `ec2:DescribeSnapshots` is denied in a region, the snapshot detector cell is `missing_permission`; existing snapshot findings in that cell remain unchanged. The region and scan remain visibly partial rather than pretending that no snapshots matched.

## Demo timeline

Demo history uses the real engine with a fixed anchor.

| Seeded scan | What the fixture demonstrates |
|---|---|
| Anchor −21 days, step 1 | First observations for long-lived EBS, EIP, stopped-instance, and snapshot conditions; the ignored volume is recorded as ignored. |
| Anchor −14 days, step 2 | Repeat observations become persistent when detector thresholds and consecutive counts are met. The temporary volume has its second observation. |
| Anchor −7 days, step 3 | The temporary volume is absent under complete coverage and resolves. The second idle Elastic IP appears for the first time. |
| Anchor −2 days, step 4 | The high-performance gp3 volume appears as newly observed; the second Elastic IP has enough history to become persistent. |

A user scan at step 5 runs at the anchor, increments continuing findings, and preserves their original first-observed timestamps.
