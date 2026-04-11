from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from pathlib import Path

from fastapi.responses import Response


@dataclass
class FaultContext:
    """Everything a fault needs. Injected by the runtime."""
    scenario: Any               # Scenario object
    spec: Any                   # shortcut to scenario.fault (FaultSpec)
    target: str                 # "llm_chat" | "mcp_tool"
    api_format: str | None = None   # "openai" | "anthropic" | None (mcp)
    request_id: Any = None          # MCP JSON-RPC id

    # Runtime-injected helpers (set by LLMRuntime / MCPRuntime)
    error_response: Callable[..., Response] | None = None
    extract_text: Callable[..., str] | None = None
    make_response: Callable[..., Any] | None = None
    corrupt_fields: Callable[..., bytes] | None = None
    body: bytes = b""               # current response body (for post-phase)
    result: dict = field(default_factory=dict)  # MCP result (for post-phase)
    # state helpers
    get_counter: Callable[..., int] | None = None


class FaultDef:
    """A fault loaded from a catalog manifest."""

    def __init__(self, manifest: dict[str, Any], catalog_dir: Path):
        self.id: str = manifest["id"]
        self.name: str = manifest.get("name", self.id)
        self.category: str = manifest.get("category", "other")
        self.severity: str = manifest.get("severity", "medium")
        self.targets: set[str] = set(manifest.get("targets", ["llm_chat", "mcp_tool"]))
        self.tags: list[str] = manifest.get("tags", [])
        self.phase: str = manifest.get("phase", "post")
        self.description: str = manifest.get("description", "caused failures the agent didn't handle")
        self.fix_hint: str = manifest.get("fix_hint", "Add error handling for this failure mode")
        self.required_fields: list[str] = manifest.get("required_fields", [])
        self.action: str | None = manifest.get("action")
        self.params: dict[str, Any] = manifest.get("params", {})
        self.handler_module: str | None = manifest.get("handler")
        self._catalog_dir = catalog_dir
        self._handler: Any = None  # lazy-loaded custom handler
        self._payloads: dict[str, str] = {}  # lazy-loaded

    def validate(self, spec: Any) -> None:
        """Validate FaultSpec fields. Raises ValueError."""
        for f in self.required_fields:
            val = getattr(spec, f, None)
            if val is None:
                raise ValueError(f"{self.id} faults require {f}")
            # Numeric fields that must be positive
            if f in ("after_count", "size_bytes") and val <= 0:
                raise ValueError(f"{self.id} faults require {f} > 0")
        # Special: latency/timeout need min_ms <= max_ms
        if self.id in ("latency", "timeout"):
            min_ms = getattr(spec, "min_ms", None)
            max_ms = getattr(spec, "max_ms", None)
            if min_ms is not None and max_ms is not None:
                if min_ms < 0 or max_ms < 0 or min_ms > max_ms:
                    raise ValueError("fault min_ms/max_ms must be valid non-negative bounds")

    def load_payload(self, name: str) -> str:
        """Load a payload file from this fault's payloads/ dir."""
        if name not in self._payloads:
            payload_dir = self._catalog_dir / "payloads"
            # Try with and without .txt extension
            for candidate in [payload_dir / f"{name}.txt", payload_dir / name]:
                if candidate.exists():
                    self._payloads[name] = candidate.read_text(encoding="utf-8").strip()
                    break
            else:
                self._payloads[name] = ""
        return self._payloads[name]

    def get_handler(self):
        """Lazy-load custom handler.py if this is a custom-phase fault."""
        if self._handler is None and self.handler_module:
            import importlib.util
            handler_path = self._catalog_dir / self.handler_module
            if handler_path.exists():
                spec = importlib.util.spec_from_file_location(
                    f"agentbreak.faults.catalog.{self.id}.handler", handler_path
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                # Find the FaultHandler subclass
                for attr in dir(mod):
                    cls = getattr(mod, attr)
                    if isinstance(cls, type) and hasattr(cls, "apply") and cls.__name__ != "FaultHandler":
                        self._handler = cls()
                        break
        return self._handler
