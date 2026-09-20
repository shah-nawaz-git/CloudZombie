# Security model

CloudZombie separates read-only runtime analysis from scripts that a human may later run outside the application.

## Guarantees

- The runtime scanner uses restricted read-only provider methods.
- Raw boto3 clients are not exposed to application logic.
- Credentials are not persisted.
- The application never performs remediation.
- Executable scripts contain only validated machine identifiers from stored findings/configuration.

## Non-guarantees

- The IAM principal may have other permissions.
- Not every dependency can be detected.
- A resource is not proven unnecessary.
- Generated remediation is not risk-free.
- A price estimate is not the final bill.
- Snapshot deletion may not free the apparent size.

## Enforcement

| Control | Implementation | Verification |
|---|---|---|
| Operation allowlist | `backend/app/providers/aws/guard.py` registers `provide-client-params.*.*` and `before-call.*.*` handlers. `_operation_name` uses botocore `signing_name` so Pricing maps to `pricing:GetProducts`. | `backend/tests/providers/test_guard.py` blocks mutating calls and permits allowlisted EC2, STS, CloudFormation, and Pricing calls. |
| Restricted wrappers | `ReadOnlyEc2`, `ReadOnlySts`, `ReadOnlyPricing`, and `ReadOnlyCloudFormation` keep clients in name-mangled attributes and expose explicit methods only. | `backend/tests/providers/test_readonly_boundary.py::test_wrapper_public_surface_is_exact` and wrapper pagination/error tests. |
| Provider boundary | Application layers receive `CloudProvider` records. Imports of boto3 and botocore belong under `app/providers/aws/`. | `backend/tests/test_import_boundary.py::test_boto_imports_are_confined_to_aws_provider`. |
| IAM equality | `ALLOWED_OPERATIONS` and `docs/iam-policy.json` describe the same 12 calls. | `backend/tests/providers/test_readonly_boundary.py::test_surface_operations_and_policy_equal_allowlist`. |
| Strict identifiers | `backend/app/remediation/validators.py` full-matches account, region, AWS IDs, UUIDs, and safe tag values. Errors redact hostile input. | `backend/tests/remediation/test_validators.py`. |
| Fail-closed script composition | `backend/app/remediation/scripts/generator.py::_assert_safe` revalidates interpolated identifiers, checks every readonly assignment, and rejects non-printable or non-ASCII output. | Generator golden, mismatch, and security tests under `backend/tests/remediation/`. |
| Metadata isolation | `ScriptService` passes only validated identifiers and settings to the generator. Finding titles, summaries, evidence, arbitrary tags, and ownership notes do not enter script composition. | `backend/tests/remediation/test_security.py::test_untrusted_finding_metadata_never_reaches_scripts`. |
| Runtime guards in scripts | Generated scripts verify account, live state, attachments or associations, ignore tags, CloudFormation tags, and exact confirmation phrases. | `backend/tests/remediation/test_behavior.py` uses `tests/remediation/fake_aws/aws` for happy and abort paths. |
| Destructive-call audit | Static scanning rejects mutating SDK-style and AWS CLI calls outside the static template boundary. | `backend/tests/test_no_mutating_calls.py`. |
| Shell quality | Static and freshly generated scripts are checked at shellcheck style severity. | `backend/tests/remediation/test_shellcheck.py`; CI `shellcheck` job. |

## Credential handling

`AwsProvider` uses the standard boto3 credential chain. `AWS_PROFILE` may be passed through directly; Docker live mode also permits the standard AWS access-key and session-token environment variables and mounts `${HOME}/.aws` read-only. Empty profile and region-selection strings are normalized to `None`.

CloudZombie does not read credential values into application models. It does not persist, log, or return access keys, secret keys, or session tokens. Identity output includes mode, account ID, principal ARN, identity type, verification time, and an error string when verification fails.

This does not prove that the IAM principal itself lacks write permission. Attach the checked-in least-privilege policy and review the principal separately.

## CORS and configuration

CORS origins come from `CLOUDZOMBIE_CORS_ORIGINS` and default to `http://localhost:3000`. The API allows `GET`, `POST`, and `PATCH`, permits only the `Content-Type` header, and does not allow credentials in CORS requests. The browser uses same-origin `/api/*` requests through the Next.js rewrite in normal deployment.

Configuration is loaded through Pydantic settings. Ignore-tag keys and values use a restricted character set. Application settings store behavior such as regions, thresholds, cache TTL, and ignore tags; they do not store AWS credentials.

## Threat model

| Threat | Control | Test |
|---|---|---|
| Runtime code calls an AWS mutation | Restricted wrappers plus session/client operation guard | `test_guard.py`, `test_readonly_boundary.py`, `test_no_mutating_calls.py` |
| A detector obtains a raw client | CloudProvider interface and import boundary | `test_import_boundary.py` and wrapper reflection |
| Hostile AWS tag/name enters executable Bash | Generator accepts typed identifiers only | `test_security.py::test_untrusted_finding_metadata_never_reaches_scripts` |
| Shell metacharacter in an identifier | Full-match validators and ASCII/readonly assertions | `test_validators.py`, `test_generator.py` |
| State changes between scan and execution | Script re-fetches live state and aborts closed | `test_behavior.py` changed-state, missing-resource, association, and attachment cases |
| Wrong account executes a script | STS identity check against validated account ID | `test_behavior.py::test_account_mismatch_aborts` |
| Resource becomes ignored or stack-owned | Runtime tag checks | ignore-tag and CloudFormation cases in `test_behavior.py` |
| Partial permission is mistaken for absence | Reconciliation ignores incomplete cells | scanner history and demo evaluation tests |
| An unsupported finding receives a destructive script | Eligibility rules restrict guarded scripts to persistent LOW-risk EBS/EIP findings | `test_eligibility.py`, `test_script_service.py` |
| Generated script drifts from reviewed output | Golden files and shellcheck | `test_golden.py`, `test_shellcheck.py` |

## Destructive-call audit

`backend/tests/test_no_mutating_calls.py` searches application Python outside `templates.py` for SDK-like names beginning with:

- `delete_`
- `terminate_`
- `release_`
- `modify_`
- `create_`
- `attach_`
- `detach_`
- `deregister_`
- `associate_`
- `disassociate_`

The literal non-AWS allowlist is intentionally small: `create_engine`, `create_database_engine`, `create_client`, `create_all`, `create_app`, and `create_scan`.

The same test searches for mutating `aws ec2` command text. `backend/app/remediation/scripts/templates.py` is the only application file allowed to contain the intended commands:

- `delete-volume`
- `release-address`
- `create-snapshot`
- `delete-snapshot`, only in a comment or an echoed commented command

The templates are static reviewed text. Do not add dynamic finding metadata to them.
