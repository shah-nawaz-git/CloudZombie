from app.models import KnownDependency
from app.providers.base import Address


def association_dependencies(address: Address) -> list[KnownDependency]:
    dependencies: list[KnownDependency] = []
    if address.instance_id:
        dependencies.append(
            KnownDependency(
                kind="eip_association",
                target_id=address.instance_id,
                description=f"Elastic IP is associated with instance {address.instance_id}.",
                blocks_remediation=True,
            )
        )
    if address.network_interface_id:
        dependencies.append(
            KnownDependency(
                kind="eip_association",
                target_id=address.network_interface_id,
                description=(
                    "Elastic IP is associated with network interface "
                    f"{address.network_interface_id}."
                ),
                blocks_remediation=True,
            )
        )
    return dependencies
