"""Tool description injection: malicious instructions hidden in tool descriptions."""
from __future__ import annotations
from typing import Any


class ToolDescriptionInjectionHandler:
    async def apply(self, ctx: Any) -> Any:
        """Marker handler — actual logic is in MCPRuntime like rug_pull."""
        return None
