"""Rug pull: mutate tool definitions after N requests.

This fault needs stateful logic (counting requests), so it uses a
custom handler instead of a declarative primitive.
"""
from __future__ import annotations
from typing import Any


class RugPullHandler:
    """Called by the runtime when phase=custom."""

    async def apply(self, ctx: Any) -> Any:
        """
        The rug pull is handled specially by MCPRuntime because it mutates
        the tools/list response, not individual tool call results.
        This handler exists as a marker — the actual logic lives in MCPRuntime
        since it needs access to the session's tools_list_call_count state.
        Returns None to signal "let the runtime handle it".
        """
        return None
