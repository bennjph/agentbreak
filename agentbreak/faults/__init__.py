from __future__ import annotations

from agentbreak.faults._base import FaultContext, FaultDef
from agentbreak.faults._registry import discover_catalog
from agentbreak.faults._primitives import PRIMITIVES

REGISTRY: dict[str, FaultDef] = discover_catalog()

def get(name: str) -> FaultDef | None:
    return REGISTRY.get(name)

def registered_kinds() -> set[str]:
    return set(REGISTRY.keys())

__all__ = ["REGISTRY", "FaultContext", "FaultDef", "PRIMITIVES", "get", "registered_kinds"]
