from datetime import datetime
from typing import Optional, Dict


def serialize_container(container, stats: Optional[Dict] = None) -> dict:
    base = {
        "id": container.id,
        "status": "running",
        "memory_limit": container.tariff.memory_limit,
        "storage_quota": container.tariff.storage_quota,
        "file_limit": container.tariff.file_limit,
        "env_label": container.env_label,
        "type_label": container.type_label,
        "created_at": datetime.now().isoformat(),
        "user_id": container.user_id,
        "commands": container.commands,
        "privileged": container.privileged,
    }
    if stats:
        base.update(stats)
    return base
