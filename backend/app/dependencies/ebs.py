from app.models import KnownDependency
from app.providers.base import Volume


def attachment_dependencies(volume: Volume) -> list[KnownDependency]:
    return [
        KnownDependency(
            kind="ec2_attachment",
            target_id=attachment.instance_id,
            description=(
                f"Volume is attached to instance {attachment.instance_id} as {attachment.device}."
            ),
            blocks_remediation=True,
        )
        for attachment in volume.attachments
    ]
