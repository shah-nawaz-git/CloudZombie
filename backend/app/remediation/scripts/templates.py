"""Static Bash text for generated CloudZombie scripts.

Everything in this module is a constant. Nothing here is rendered from finding
evidence, tags, names or descriptions: the generator only prepends a header of
``readonly NAME="<validated identifier>"`` assignments (see generator.py) and the
bodies below reference those variables. Keep it that way — the security boundary
of script generation depends on it.

The bodies target Bash 3.2+ (macOS default) and are kept shellcheck-clean.
"""

SHEBANG = "#!/usr/bin/env bash\n"

STRICT_MODE = "set -euo pipefail\n"

# Helpers shared by every script -------------------------------------------------------------

COMMON_FUNCTIONS = r"""
abort() {
  echo
  echo "ABORTED"
  echo
  echo "$1"
  echo
  echo "No action performed."
  exit 1
}

to_lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

require_aws_cli() {
  if ! command -v aws >/dev/null 2>&1; then
    abort "The AWS CLI (aws) is not installed or not on PATH."
  fi
}

verify_account() {
  local current_account
  if ! current_account="$(aws sts get-caller-identity --region "$REGION" --query Account --output text 2>/dev/null)"; then
    abort "Could not determine the current AWS account (aws sts get-caller-identity failed). Check your credentials."
  fi
  if [ "$current_account" != "$EXPECTED_ACCOUNT_ID" ]; then
    abort "Account mismatch.

Expected account: $EXPECTED_ACCOUNT_ID
Current account:  $current_account"
  fi
  echo "Account verified: $current_account"
}
"""

# Unattached EBS volume: guarded deletion ----------------------------------------------------

EBS_DELETE_BODY = r"""
verify_volume_state() {
  local state attachment_count
  if ! state="$(aws ec2 describe-volumes --region "$REGION" --volume-ids "$VOLUME_ID" --query 'Volumes[0].State' --output text 2>/dev/null)"; then
    abort "Volume $VOLUME_ID was not found in $REGION. It may already have been deleted."
  fi
  if [ "$state" != "available" ]; then
    abort "Resource state changed since CloudZombie analysis.

Expected volume state: available
Current volume state:  $state"
  fi
  attachment_count="$(aws ec2 describe-volumes --region "$REGION" --volume-ids "$VOLUME_ID" --query 'length(Volumes[0].Attachments)' --output text)"
  if [ "$attachment_count" != "0" ]; then
    abort "Resource state changed since CloudZombie analysis.

The volume now reports $attachment_count attachment(s)."
  fi
  echo "Volume state verified: available with 0 attachments"
}

verify_volume_tags() {
  local ignore_value stack_name
  ignore_value="$(aws ec2 describe-volumes --region "$REGION" --volume-ids "$VOLUME_ID" --query "Volumes[0].Tags[?Key=='${IGNORE_TAG_KEY}'].Value | [0]" --output text)"
  if [ "$ignore_value" != "None" ] && [ "$(to_lower "$ignore_value")" = "$(to_lower "$IGNORE_TAG_VALUE")" ]; then
    abort "Resource is now marked to be ignored ($IGNORE_TAG_KEY=$ignore_value)."
  fi
  stack_name="$(aws ec2 describe-volumes --region "$REGION" --volume-ids "$VOLUME_ID" --query "Volumes[0].Tags[?Key=='${CLOUDFORMATION_TAG_KEY}'].Value | [0]" --output text)"
  if [ "$stack_name" != "None" ] && [ -n "$stack_name" ]; then
    abort "Resource now carries the $CLOUDFORMATION_TAG_KEY tag (stack: $stack_name). Change the CloudFormation stack instead of deleting the volume manually."
  fi
  echo "Ignore-tag check passed; no CloudFormation stack tag present"
}

show_current_volume() {
  echo
  echo "Current volume as reported by AWS right now:"
  aws ec2 describe-volumes --region "$REGION" --volume-ids "$VOLUME_ID" --output table
  echo
  echo "Ownership note: CloudZombie found no CloudFormation evidence for this volume, but"
  echo "that does not prove it is unmanaged. Terraform or other tooling may still own it."
}

offer_snapshot() {
  local answer snapshot_id
  echo
  printf 'Create a snapshot of %s before deleting it? [y/N] ' "$VOLUME_ID"
  read -r answer
  case "$answer" in
    y|Y)
      if ! snapshot_id="$(aws ec2 create-snapshot --region "$REGION" --volume-id "$VOLUME_ID" --description "CloudZombie pre-deletion snapshot" --query SnapshotId --output text)"; then
        abort "Snapshot creation failed; the volume was not deleted."
      fi
      echo "Waiting for snapshot $snapshot_id to complete..."
      if ! aws ec2 wait snapshot-completed --region "$REGION" --snapshot-ids "$snapshot_id"; then
        abort "Snapshot $snapshot_id did not complete; the volume was not deleted."
      fi
      echo "Snapshot $snapshot_id completed. It incurs snapshot storage charges until you delete it."
      ;;
    *)
      echo "No snapshot will be created."
      ;;
  esac
}

confirm_deletion() {
  local confirmation
  echo
  echo "This will permanently delete EBS volume $VOLUME_ID in $REGION (account $EXPECTED_ACCOUNT_ID)."
  printf 'Type DELETE %s to continue: ' "$VOLUME_ID"
  read -r confirmation
  if [ "$confirmation" != "DELETE $VOLUME_ID" ]; then
    abort "Confirmation did not match."
  fi
}

main() {
  require_aws_cli
  verify_account
  verify_volume_state
  verify_volume_tags
  show_current_volume
  offer_snapshot
  confirm_deletion
  aws ec2 delete-volume --region "$REGION" --volume-id "$VOLUME_ID"
  echo
  echo "Deleted volume $VOLUME_ID in $REGION."
}

main "$@"
"""

# Unassociated Elastic IP: guarded release ---------------------------------------------------

EIP_RELEASE_BODY = r"""
verify_address_state() {
  local association_id instance_id network_interface_id
  if ! association_id="$(aws ec2 describe-addresses --region "$REGION" --allocation-ids "$ALLOCATION_ID" --query 'Addresses[0].AssociationId' --output text 2>/dev/null)"; then
    abort "Elastic IP allocation $ALLOCATION_ID was not found in $REGION. It may already have been released."
  fi
  instance_id="$(aws ec2 describe-addresses --region "$REGION" --allocation-ids "$ALLOCATION_ID" --query 'Addresses[0].InstanceId' --output text)"
  network_interface_id="$(aws ec2 describe-addresses --region "$REGION" --allocation-ids "$ALLOCATION_ID" --query 'Addresses[0].NetworkInterfaceId' --output text)"
  if [ "$association_id" != "None" ] || [ "$instance_id" != "None" ] || [ "$network_interface_id" != "None" ]; then
    abort "Resource state changed since CloudZombie analysis.

The address is now associated.
AssociationId:      $association_id
InstanceId:         $instance_id
NetworkInterfaceId: $network_interface_id"
  fi
  echo "Address state verified: not associated with any instance or network interface"
}

verify_address_tags() {
  local ignore_value stack_name
  ignore_value="$(aws ec2 describe-addresses --region "$REGION" --allocation-ids "$ALLOCATION_ID" --query "Addresses[0].Tags[?Key=='${IGNORE_TAG_KEY}'].Value | [0]" --output text)"
  if [ "$ignore_value" != "None" ] && [ "$(to_lower "$ignore_value")" = "$(to_lower "$IGNORE_TAG_VALUE")" ]; then
    abort "Resource is now marked to be ignored ($IGNORE_TAG_KEY=$ignore_value)."
  fi
  stack_name="$(aws ec2 describe-addresses --region "$REGION" --allocation-ids "$ALLOCATION_ID" --query "Addresses[0].Tags[?Key=='${CLOUDFORMATION_TAG_KEY}'].Value | [0]" --output text)"
  if [ "$stack_name" != "None" ] && [ -n "$stack_name" ]; then
    abort "Resource now carries the $CLOUDFORMATION_TAG_KEY tag (stack: $stack_name). Change the CloudFormation stack instead of releasing the address manually."
  fi
  echo "Ignore-tag check passed; no CloudFormation stack tag present"
}

show_current_address() {
  echo
  echo "Current Elastic IP as reported by AWS right now:"
  aws ec2 describe-addresses --region "$REGION" --allocation-ids "$ALLOCATION_ID" --output table
  echo
  echo "WARNING: releasing an Elastic IP returns it to the AWS pool. You may not be able to"
  echo "recover the same public IPv4 address afterwards. Check DNS records and allow-lists first."
  echo
  echo "Ownership note: CloudZombie found no CloudFormation evidence for this address, but"
  echo "that does not prove it is unmanaged. Terraform or other tooling may still own it."
}

confirm_release() {
  local confirmation
  echo
  echo "This will release Elastic IP allocation $ALLOCATION_ID in $REGION (account $EXPECTED_ACCOUNT_ID)."
  printf 'Type RELEASE %s to continue: ' "$ALLOCATION_ID"
  read -r confirmation
  if [ "$confirmation" != "RELEASE $ALLOCATION_ID" ]; then
    abort "Confirmation did not match."
  fi
}

main() {
  require_aws_cli
  verify_account
  verify_address_state
  verify_address_tags
  show_current_address
  confirm_release
  aws ec2 release-address --region "$REGION" --allocation-id "$ALLOCATION_ID"
  echo
  echo "Released Elastic IP allocation $ALLOCATION_ID in $REGION."
}

main "$@"
"""

# Investigation scripts (read-only) ----------------------------------------------------------

INVESTIGATION_PREAMBLE = r"""
investigation_banner() {
  echo
  echo "CloudZombie investigation script (read-only)."
  echo "This script only runs describe-* commands. It performs no changes."
  echo
}
"""

EBS_INVESTIGATION_BODY = r"""
main() {
  require_aws_cli
  verify_account
  investigation_banner
  echo "Volume $VOLUME_ID in $REGION:"
  aws ec2 describe-volumes --region "$REGION" --volume-ids "$VOLUME_ID" --output table
  echo
  echo "Snapshots created from this volume (owned by this account):"
  aws ec2 describe-snapshots --region "$REGION" --owner-ids self --filters "Name=volume-id,Values=$VOLUME_ID" --output table
  echo
  echo "No guarded deletion script is offered for this finding yet (see the cleanup plan for the reason)."
}

main "$@"
"""

EIP_INVESTIGATION_BODY = r"""
main() {
  require_aws_cli
  verify_account
  investigation_banner
  echo "Elastic IP allocation $ALLOCATION_ID in $REGION:"
  aws ec2 describe-addresses --region "$REGION" --allocation-ids "$ALLOCATION_ID" --output table
  echo
  echo "No guarded release script is offered for this finding yet (see the cleanup plan for the reason)."
}

main "$@"
"""

EC2_INVESTIGATION_BODY = r"""
main() {
  require_aws_cli
  verify_account
  investigation_banner
  echo "Instance $INSTANCE_ID in $REGION:"
  aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" --output table
  echo
  echo "EBS volumes attached to the instance (billed while it is stopped):"
  aws ec2 describe-volumes --region "$REGION" --filters "Name=attachment.instance-id,Values=$INSTANCE_ID" --output table
  echo
  echo "Elastic IP addresses associated with the instance (billed while it is stopped):"
  aws ec2 describe-addresses --region "$REGION" --filters "Name=instance-id,Values=$INSTANCE_ID" --output table
  echo
  echo "CloudZombie does not generate termination commands. Confirm with the instance owner"
  echo "whether it is still needed, and evaluate the attached volumes and addresses separately."
}

main "$@"
"""

SNAPSHOT_INVESTIGATION_BODY = r"""
# REVIEW REQUIRED - deletion is intentionally disabled in this script.
# Only after confirming that no AMI, sharing, backup plan or lock depends on the
# snapshot, and understanding that incremental snapshots may free less than their
# apparent size, you may run the following command yourself:
# aws ec2 delete-snapshot --region "$REGION" --snapshot-id "$SNAPSHOT_ID"

main() {
  require_aws_cli
  verify_account
  investigation_banner
  echo "Snapshot $SNAPSHOT_ID in $REGION:"
  aws ec2 describe-snapshots --region "$REGION" --snapshot-ids "$SNAPSHOT_ID" --output table
  echo
  echo "Sharing (createVolumePermission):"
  aws ec2 describe-snapshot-attribute --region "$REGION" --snapshot-id "$SNAPSHOT_ID" --attribute createVolumePermission --output table
  echo
  echo "AMIs owned by this account that reference the snapshot:"
  aws ec2 describe-images --region "$REGION" --owners self --filters "Name=block-device-mapping.snapshot-id,Values=$SNAPSHOT_ID" --output table
  echo
  echo "Snapshot lock status:"
  aws ec2 describe-locked-snapshots --region "$REGION" --snapshot-ids "$SNAPSHOT_ID" --output table || echo "(lock status unavailable)"
  echo
  echo "Snapshots are incremental: deleting this snapshot may free less storage than its"
  echo "apparent size. Only blocks not referenced by other snapshots are reclaimed."
  echo
  echo "REVIEW REQUIRED - deletion is intentionally disabled in this script."
  echo "If, after review, you decide to delete the snapshot, run the command below manually:"
  echo "#   aws ec2 delete-snapshot --region \"$REGION\" --snapshot-id \"$SNAPSHOT_ID\""
}

main "$@"
"""

# Bulk guarded script --------------------------------------------------------------------------

BULK_FUNCTIONS = r"""
SKIPPED=0
COMPLETED=0

skip() {
  echo
  echo "SKIPPED $1"
  echo "$2"
  echo "No action performed for $1."
  SKIPPED=$((SKIPPED + 1))
}

check_tags() {
  local describe_command="$1" id_flag="$2" region="$3" resource_id="$4" root="$5"
  local ignore_value stack_name
  ignore_value="$(aws ec2 "$describe_command" --region "$region" "$id_flag" "$resource_id" --query "${root}[0].Tags[?Key=='${IGNORE_TAG_KEY}'].Value | [0]" --output text)"
  if [ "$ignore_value" != "None" ] && [ "$(to_lower "$ignore_value")" = "$(to_lower "$IGNORE_TAG_VALUE")" ]; then
    echo "Resource is now marked to be ignored ($IGNORE_TAG_KEY=$ignore_value)."
    return 1
  fi
  stack_name="$(aws ec2 "$describe_command" --region "$region" "$id_flag" "$resource_id" --query "${root}[0].Tags[?Key=='${CLOUDFORMATION_TAG_KEY}'].Value | [0]" --output text)"
  if [ "$stack_name" != "None" ] && [ -n "$stack_name" ]; then
    echo "Resource now carries the $CLOUDFORMATION_TAG_KEY tag (stack: $stack_name)."
    return 1
  fi
  return 0
}

process_volume() {
  local region="$1" volume_id="$2" state attachment_count confirmation reason
  echo
  echo "=== EBS volume $volume_id ($region) ==="
  if ! state="$(aws ec2 describe-volumes --region "$region" --volume-ids "$volume_id" --query 'Volumes[0].State' --output text 2>/dev/null)"; then
    skip "$volume_id" "Volume not found in $region."
    return 0
  fi
  if [ "$state" != "available" ]; then
    skip "$volume_id" "Resource state changed since CloudZombie analysis (state: $state)."
    return 0
  fi
  attachment_count="$(aws ec2 describe-volumes --region "$region" --volume-ids "$volume_id" --query 'length(Volumes[0].Attachments)' --output text)"
  if [ "$attachment_count" != "0" ]; then
    skip "$volume_id" "Resource state changed since CloudZombie analysis ($attachment_count attachment(s))."
    return 0
  fi
  if ! reason="$(check_tags describe-volumes --volume-ids "$region" "$volume_id" Volumes)"; then
    skip "$volume_id" "$reason"
    return 0
  fi
  aws ec2 describe-volumes --region "$region" --volume-ids "$volume_id" --output table
  printf 'Type DELETE %s to delete this volume (anything else skips it): ' "$volume_id"
  read -r confirmation
  if [ "$confirmation" != "DELETE $volume_id" ]; then
    skip "$volume_id" "Confirmation did not match."
    return 0
  fi
  aws ec2 delete-volume --region "$region" --volume-id "$volume_id"
  echo "Deleted volume $volume_id in $region."
  COMPLETED=$((COMPLETED + 1))
}

process_address() {
  local region="$1" allocation_id="$2" association_id instance_id network_interface_id confirmation reason
  echo
  echo "=== Elastic IP $allocation_id ($region) ==="
  if ! association_id="$(aws ec2 describe-addresses --region "$region" --allocation-ids "$allocation_id" --query 'Addresses[0].AssociationId' --output text 2>/dev/null)"; then
    skip "$allocation_id" "Allocation not found in $region."
    return 0
  fi
  instance_id="$(aws ec2 describe-addresses --region "$region" --allocation-ids "$allocation_id" --query 'Addresses[0].InstanceId' --output text)"
  network_interface_id="$(aws ec2 describe-addresses --region "$region" --allocation-ids "$allocation_id" --query 'Addresses[0].NetworkInterfaceId' --output text)"
  if [ "$association_id" != "None" ] || [ "$instance_id" != "None" ] || [ "$network_interface_id" != "None" ]; then
    skip "$allocation_id" "Resource state changed since CloudZombie analysis (address is now associated)."
    return 0
  fi
  if ! reason="$(check_tags describe-addresses --allocation-ids "$region" "$allocation_id" Addresses)"; then
    skip "$allocation_id" "$reason"
    return 0
  fi
  aws ec2 describe-addresses --region "$region" --allocation-ids "$allocation_id" --output table
  echo "WARNING: a released Elastic IP may not be recoverable."
  printf 'Type RELEASE %s to release this address (anything else skips it): ' "$allocation_id"
  read -r confirmation
  if [ "$confirmation" != "RELEASE $allocation_id" ]; then
    skip "$allocation_id" "Confirmation did not match."
    return 0
  fi
  aws ec2 release-address --region "$region" --allocation-id "$allocation_id"
  echo "Released Elastic IP allocation $allocation_id in $region."
  COMPLETED=$((COMPLETED + 1))
}

bulk_summary() {
  echo
  echo "Completed: $COMPLETED   Skipped: $SKIPPED"
}
"""

BULK_MAIN_OPEN = r"""
main() {
  require_aws_cli
  verify_account
"""

BULK_MAIN_CLOSE = r"""  bulk_summary
}

main "$@"
"""
