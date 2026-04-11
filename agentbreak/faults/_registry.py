from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentbreak.faults._base import FaultDef


def discover_catalog(catalog_dir: Path | None = None) -> dict[str, FaultDef]:
    """Scan catalog/ for manifest.yaml files, return {id: FaultDef}."""
    if catalog_dir is None:
        catalog_dir = Path(__file__).parent / "catalog"
    registry: dict[str, FaultDef] = {}
    if not catalog_dir.exists():
        return registry
    for manifest_path in sorted(catalog_dir.rglob("manifest.yaml")):
        try:
            with manifest_path.open("r", encoding="utf-8") as f:
                manifest = yaml.safe_load(f)
            if not isinstance(manifest, dict) or "id" not in manifest:
                continue
            fault_dir = manifest_path.parent
            fault_def = FaultDef(manifest, fault_dir)
            registry[fault_def.id] = fault_def
        except Exception:
            continue  # skip malformed manifests
    return registry
