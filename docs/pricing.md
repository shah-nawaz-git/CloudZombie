# Pricing methodology

CloudZombie estimates **monthly public list-price exposure**. The estimate is not a customer bill and is never described as savings.

## Backend order

With `pricing_mode=auto`, CloudZombie tries:

1. AWS Pricing API through `CloudProvider.get_prices`.
2. The checked-in fallback table.

`fallback_only` skips the API. Demo mode forces fallback-only pricing. `disabled` returns an unavailable estimate. Backend failures become coverage warnings and pricing falls through rather than failing detection.

## AWS Pricing API

The Pricing client always uses the `us-east-1` endpoint. Product lookups add a `regionCode` `TERM_MATCH` filter for the resource region.

The implementation uses:

- AmazonEC2, product family `Storage`, and `volumeApiName` for EBS storage (`GB-Mo`).
- AmazonEC2, product family `System Operation`, and `volumeApiName` for provisioned IOPS (`IOPS-Mo`) and gp3 throughput (`MiBps-Mo`). When a unit is absent, usage types containing `VolumeP-IOPS` or `VolumeP-Throughput` provide the fallback match.
- AmazonEC2, product family `Storage Snapshot`, with usage types ending in `EBS:SnapshotUsage` or `EBS:SnapshotArchiveStorage` (`GB-Mo`).
- AmazonVPC, product family `IP Address`, with usage type ending in `PublicIPv4:IdleAddress` (`Hrs`).

On-Demand price dimensions provide USD unit prices. io2 dimensions are sorted by `beginRange` and calculated as progressive tiers; unparseable or missing products, dimensions, ranges, or prices raise a lookup error and permit fallback.

## Cache

Pricing API unit prices are cached through a `PricingCache` protocol. Production wiring uses `DbPricingCache`, backed by the `pricing_cache` table:

```text
cache_key, payload JSON, fetched_at, source
```

Decimals are stored as strings in JSON. Cache hits retain the original retrieval timestamp. Expired rows are ignored according to `pricing_cache_ttl_seconds`, 86,400 seconds by default. An in-memory TTL cache is available for tests and isolated use.

## Fallback table

The fallback table is `backend/app/pricing/fallback_prices.json`, captured at **2026-09-20**. Unknown regions use `us-east-1` values and the explanation says so.

### us-east-1

| Item | USD unit price |
|---|---:|
| gp3 storage / IOPS over 3,000 / throughput over 125 MiB/s | 0.08 GiB-month / 0.005 IOPS-month / 0.04 MiB/s-month |
| gp2 storage | 0.10 GiB-month |
| io1 storage / IOPS | 0.125 GiB-month / 0.065 IOPS-month |
| io2 storage / IOPS tiers | 0.125 GiB-month / 0.065, 0.046, 0.032 IOPS-month |
| st1 | 0.045 GiB-month |
| sc1 | 0.015 GiB-month |
| standard magnetic | 0.05 GiB-month |
| standard snapshot | 0.05 GiB-month |
| archive snapshot | 0.0125 GiB-month |
| public IPv4 | 0.005 per hour |

### eu-central-1

| Item | USD unit price |
|---|---:|
| gp3 storage / IOPS over 3,000 / throughput over 125 MiB/s | 0.0952 GiB-month / 0.006 IOPS-month / 0.0476 MiB/s-month |
| gp2 storage | 0.119 GiB-month |
| io1 storage / IOPS | 0.149 GiB-month / 0.078 IOPS-month |
| io2 storage / IOPS tiers | 0.149 GiB-month / 0.078, 0.055, 0.038 IOPS-month |
| st1 | 0.054 GiB-month |
| sc1 | 0.018 GiB-month |
| standard magnetic | 0.059 GiB-month |
| standard snapshot | 0.054 GiB-month |
| archive snapshot | 0.0135 GiB-month |
| public IPv4 | 0.005 per hour |

Sources used when assembling the fallback data:

- <https://aws.amazon.com/ebs/pricing/>
- <https://aws.amazon.com/ebs/volume-types/>
- <https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-archive-pricing.html>
- <https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights/>
- <https://aws-pricing.com/eu-central-1.html> for Frankfurt figures

## Calculations

### EBS volumes

- gp3: `size × storage + max(iops − 3000, 0) × IOPS + max(throughput − 125, 0) × throughput`.
- io1: `size × storage + provisioned IOPS × IOPS price`.
- io2: `size × storage + provisioned IOPS across progressive tiers`.
- gp2, st1, sc1, and standard: `size × storage`.

### Elastic IP

`public IPv4 hourly price × 730 hours`.

### Snapshot

`reported snapshot size × standard or archive GiB-month price`.

This is always a LOW-confidence upper bound because snapshots are incremental and AWS does not expose exact independently reclaimable blocks through these calls.

### Stopped EC2 instance

Sum estimates for known attached EBS volumes plus associated public IPv4 addresses. Stopped compute is not billed and is not included.

## Confidence

| Source or condition | Confidence |
|---|---|
| AWS Pricing API | HIGH |
| Fallback table | MEDIUM |
| Snapshot estimate from either source | LOW, upper bound |
| No calculable unit prices | UNAVAILABLE |

The scan headline sums open findings with HIGH or MEDIUM confidence. LOW-confidence potential exposure is stored and displayed separately.

## Exclusions

The estimate excludes:

- Standard magnetic volume per-I/O charges.
- Data transfer.
- Stopped EC2 compute.
- Taxes, discounts, Savings Plans, Reserved Instance effects, credits, and negotiated rates.
- Exact incremental snapshot reclaimability.

Use the wording **estimated monthly list-price exposure** or **estimated monthly cleanup opportunity**. Do not describe the value as savings.
