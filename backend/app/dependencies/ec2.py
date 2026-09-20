from app.models import KnownDependency
from app.providers.base import Address, Instance, Volume


def stopped_instance_dependencies(
    instance: Instance, volumes: list[Volume], addresses: list[Address]
) -> list[KnownDependency]:
    dependencies = [
        KnownDependency(
            kind="attached_ebs_volume",
            target_id=volume.volume_id,
            description=(
                f"Attached EBS volume {volume.volume_id} ({volume.size_gib} GiB "
                f"{volume.volume_type}) continues to be billed while the instance is stopped."
            ),
            blocks_remediation=False,
        )
        for volume in volumes
    ]
    dependencies.extend(
        KnownDependency(
            kind="associated_elastic_ip",
            target_id=address.allocation_id,
            description=(
                f"Associated Elastic IP {address.allocation_id} continues to be billed while "
                f"instance {instance.instance_id} is stopped."
            ),
            blocks_remediation=False,
        )
        for address in addresses
        if address.allocation_id is not None
    )
    return dependencies
