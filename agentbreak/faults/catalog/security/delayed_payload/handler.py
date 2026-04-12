"""Delayed payload: behave normally for N calls, then inject adversarial content."""
from __future__ import annotations
from typing import Any


class DelayedPayloadHandler:
    async def apply(self, ctx: Any) -> Any:
        """Marker handler — actual counting logic lives in MCPRuntime."""
        return None
