from __future__ import annotations

import asyncio
import json
import random
from typing import Any

from agentbreak.faults._base import FaultContext


async def delay(ctx: FaultContext, params: dict[str, Any]) -> None:
    """Sleep for random duration between min_ms and max_ms."""
    min_ms = params.get("min_ms") or ctx.spec.min_ms or 0
    max_ms = params.get("max_ms") or ctx.spec.max_ms or min_ms
    ms = random.uniform(min_ms, max_ms)
    await asyncio.sleep(ms / 1000)


def return_error(ctx: FaultContext, params: dict[str, Any]) -> Any:
    """Return an HTTP error response."""
    status = params.get("status") or ctx.spec.status_code or 500
    if ctx.error_response:
        return ctx.error_response(status)
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=status, content={"error": f"AgentBreak injected {status}"})


def replace_body(ctx: FaultContext, params: dict[str, Any]) -> bytes:
    """Replace the entire response body."""
    content = params.get("content", "")
    return content.encode("utf-8") if isinstance(content, str) else content


def inject_text(ctx: FaultContext, params: dict[str, Any]) -> Any:
    """Append or prepend text to the response content."""
    # Resolve text from payload file or inline
    text = params.get("text", "")
    if not text and params.get("payload_dir"):
        # Load from payload file based on spec field
        poison_type = ctx.spec.poison_type or params.get("default_payload", "").replace(".txt", "")
        if poison_type and hasattr(ctx, "_fault_def") and ctx._fault_def:
            text = ctx._fault_def.load_payload(poison_type)
    if not text:
        text = ctx.spec.payload or ""

    original = ctx.extract_text() if ctx.extract_text else ""
    position = params.get("position", "append")
    if position == "prepend":
        combined = f"{text}\n\n{original}" if original else text
    else:
        combined = f"{original}\n\n{text}" if original else text

    if ctx.make_response:
        return ctx.make_response(combined)
    return combined.encode("utf-8")


def corrupt_json(ctx: FaultContext, params: dict[str, Any]) -> bytes:
    """Return syntactically broken JSON."""
    return b"{not valid"


def corrupt_schema(ctx: FaultContext, params: dict[str, Any]) -> Any:
    """Return valid JSON with broken structure."""
    if ctx.corrupt_fields:
        return ctx.corrupt_fields()
    return b'{"content": "INVALID"}'


def large_body(ctx: FaultContext, params: dict[str, Any]) -> Any:
    """Replace content with oversized text."""
    size = params.get("size_bytes") or ctx.spec.size_bytes or 1024
    chunk = "AgentBreak large response. "
    repeats = max(1, (size // len(chunk)) + 1)
    text = (chunk * repeats)[:size]
    if ctx.make_response:
        return ctx.make_response(text)
    return text.encode("utf-8")


def wrong_content(ctx: FaultContext, params: dict[str, Any]) -> Any:
    """Replace content with unrelated text."""
    text = params.get("text") or ctx.spec.body or "AgentBreak injected wrong content."
    if ctx.make_response:
        return ctx.make_response(text)
    return text.encode("utf-8")


# Map action names to functions
PRIMITIVES: dict[str, Any] = {
    "delay": delay,
    "return_error": return_error,
    "replace_body": replace_body,
    "inject_text": inject_text,
    "corrupt_json": corrupt_json,
    "corrupt_schema": corrupt_schema,
    "large_body": large_body,
    "wrong_content": wrong_content,
}
