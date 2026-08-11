from __future__ import annotations

import hashlib
import json
from importlib import resources
from pathlib import Path

from migration_lantern_scan.models import PublicRegistry


def load_registry(path: Path | None = None) -> PublicRegistry:
    if path is None:
        content = (
            resources.files("migration_lantern_scan")
            .joinpath("data/rules.json")
            .read_text(encoding="utf-8")
        )
    else:
        content = path.read_text(encoding="utf-8")
    return PublicRegistry.model_validate_json(content)


def registry_digest(registry: PublicRegistry) -> str:
    canonical = json.dumps(
        registry.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()
