"""Schema rug pull: tool input schema mutates after N requests."""
from __future__ import annotations
from typing import Any


class SchemaRugPullHandler:
    async def apply(self, ctx: Any) -> Any:
        """Marker handler — actual logic lives in MCPRuntime."""
        return None
