# API reference

The FastAPI application serves interactive documentation at `/api/docs` and the machine-readable schema at `/api/openapi.json`.

All routes use the `/api` prefix. Money fields in scan and finding responses are JSON numbers rounded to the database's four-decimal precision; internal persistence uses `Decimal`.

## Endpoints

| Method | Path | Purpose | Key parameters |
|---|---|---|---|
| GET | `/api/health` | Check application and database health | None |
| GET | `/api/identity` | Return mode and verified AWS/demo identity | `refresh=true` re-queries the provider |
| POST | `/api/scans` | Create a scan and optionally wait for completion | JSON `regions?: string[]`, `wait?: boolean`; returns 202 |
| GET | `/api/scans` | List recent scans | `limit`, default 50 |
| GET | `/api/scans/{scan_id}` | Get one scan and its coverage payload | UUID path parameter |
| GET | `/api/findings` | Filter, sort, and paginate findings | `resource_type`, `region`, repeatable `status`, `detection_confidence`, `remediation_risk`, `cost_confidence`, `ownership`, `persistence_state`, first-observed bounds, `min_observation_count`, `q`, `sort`, `order`, `page`, `page_size` |
| GET | `/api/findings/{finding_id}` | Finding detail, observations, and related findings | UUID path parameter |
| PATCH | `/api/findings/{finding_id}` | Dismiss an open finding or reopen a dismissed one | JSON `status: dismissed|open`, optional `reason` up to 500 characters |
| GET | `/api/findings/{finding_id}/plan` | Build the cleanup plan | UUID path parameter |
| GET | `/api/findings/{finding_id}/script` | Generate the current guarded or investigation script | `format=json|raw`; raw returns `text/x-shellscript` with attachment filename |
| POST | `/api/scripts/bulk` | Generate one guarded bulk script from eligible findings | JSON `finding_ids`, 1–200 UUIDs |
| GET | `/api/history` | Per-scan observation and exposure series | `limit`, default 50 |
| GET | `/api/coverage` | Latest non-running coverage matrix | None |
| GET | `/api/overview` | Current totals, latest scan, coverage summary, and resource breakdowns | None |
| GET | `/api/settings` | Validated application settings, mode, and threshold help | None |
| PATCH | `/api/settings` | Update patchable settings | Regions, detector thresholds, consecutive minimum, ignore tags, pricing mode/cache TTL, region concurrency; demo anchor is not patchable |

## Finding computed fields

Finding responses include stored columns plus:

- `resource_age_days`
- `first_observed_days_ago`
- `last_observed_days_ago`
- `observation_age_days`
- `days_until_persistent`
- `threshold_days`
- `script_kind`
- `script_available`
- `script_unavailable_reason`

`observation_age_days` is streak persistence, not days since the first lifetime observation.

## History and overview

History points include observed counts and exposure grouped by resource type. Exposure uses observation-time cost confidence stored in `finding_observations.cost_confidence_at_observation`; only open HIGH/MEDIUM observations contribute to headline exposure.

Overview returns latest scan data, running state, cleanup opportunity, separate low-confidence potential exposure, status/risk/persistence totals, region coverage counts, and resource-type breakdowns.

## Errors

CloudZombie's application errors use:

```json
{
  "detail": {
    "code": "not_found",
    "message": "Finding ... was not found."
  }
}
```

Known mappings:

| HTTP | Code | Meaning |
|---:|---|---|
| 404 | `not_found` | Requested scan, finding, or coverage does not exist |
| 409 | `scan_running` | Another scan is active |
| 409 | `invalid_transition` | Finding status transition is not allowed |
| 422 | `invalid_identifier` | Stored/configured machine identifier failed strict validation |
| 502 | `aws_error` | AWS provider operation failed |
| 503 | `aws_credentials` | AWS credentials could not be resolved or verified; includes a configuration hint |

FastAPI request validation failures retain the default 422 validation-error shape.
