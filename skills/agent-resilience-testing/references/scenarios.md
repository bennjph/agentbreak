# Scenario Reference

Use this when writing or reviewing `.agentbreak/scenarios.yaml`.

## Shape

```yaml
version: 1
preset: standard-all
scenarios:
  - name: search-tool-timeout
    summary: search_docs times out
    target: mcp_tool
    match:
      tool_name: search_docs
    fault:
      kind: timeout
      min_ms: 5000
      max_ms: 10000
    schedule:
      mode: random
      probability: 0.2
    tags: [mcp, reliability]
```

## Supported Targets

- `llm_chat`: OpenAI chat completions and Anthropic messages.
- `mcp_tool`: MCP tool calls, resource reads, and prompt gets.

Other target names may appear in future-facing type hints, but current validation only supports `llm_chat` and `mcp_tool`.

## Presets

- `standard`: 6 baseline LLM scenarios.
- `standard-mcp`: 7 baseline MCP scenarios.
- `standard-all`: `standard` plus `standard-mcp`.
- `brownout`: LLM latency and rate-limit stress.
- `mcp-slow-tools`: high-probability MCP latency.
- `mcp-tool-failures`: MCP 503 failures.
- `mcp-mixed-transient`: light MCP latency and errors.
- `mcp-security`: prompt injection, exfiltration, cross-tool manipulation, many-shot jailbreak, and rug pull.

Keep presets in place and append project-specific scenarios under `scenarios:`.

## Resilience Profile

When the user asks for a full resilience test, generate scenarios across these groups if the target surface exists:

- **LLM infrastructure:** `http_error`, `rate_limit_retry_after`, `overloaded`, `connection_reset`, `cdn_interception`, `not_found`, `auth_error`, `token_expiry`
- **Brownouts:** `brownout`, `latency`, `packet_jitter`, `idle_timeout`, `intermittent_flapping`
- **Context/token pressure:** `finish_reason_length`, `request_too_large`, `truncated_context`, `partial_tool_call`, `large_response`
- **Malformed outputs:** `invalid_json`, `schema_violation`, `wrong_content`, `wrong_content_type`, `empty_response`, `unicode_corruption`
- **Streaming:** `stream_truncation`, `stream_mid_error`, `stream_malformed_chunk`
- **Prompt injection:** `direct_prompt_override`, `system_prompt_extraction`, `encoding_evasion`, `invisible_text`, `role_play_injection`
- **MCP reliability:** `timeout`, `tool_error_result`, `jsonrpc_error`, `tool_schema_drift`, `tools_list_empty`, `tools_list_partial`
- **MCP security:** `tool_poisoning`, `data_exfiltration`, `confused_deputy`, `cross_server_shadowing`, `tool_description_injection`, `rug_pull`, `rug_pull_schema`

Prefer 8-15 focused scenarios per first run. Do not dump the whole catalog unless the user asks for exhaustive testing.

## Match Filters

- `model`: exact model name on LLM requests.
- `tool_name`: exact MCP tool/resource/prompt name.
- `tool_name_pattern`: glob pattern such as `search_*`.
- `route`: exact request path.
- `method`: HTTP method or MCP JSON-RPC method.

All specified filters must match.

## Fault Fields

Fault kinds are discovered from `agentbreak/faults/catalog/`, so prefer the docs and `agentbreak validate` over hardcoded assumptions. Common fields:

- `http_error`: requires `status_code`.
- `latency` and `timeout`: require `min_ms` and `max_ms`; `timeout` is MCP-only in the built-in catalog.
- `large_response`: requires `size_bytes`.
- `wrong_content`: optional `body`.
- `tool_poisoning`: requires `poison_type` of `prompt_injection`, `exfiltration`, `cross_tool`, or `many_shot`; optional `payload`; MCP-only.
- `rug_pull`: requires positive `after_count`; MCP-only.

For less common fault kinds, inspect `agentbreak/faults/catalog/<category>/<fault>/manifest.yaml` and use required fields from the manifest.

## Schedules

- `always`: every matching request.
- `random`: requires `probability` from `0.0` to `1.0`.
- `periodic`: requires `every > 0`, `length > 0`, and `length <= every`.

## Query Generation

When creating `.agentbreak/queries.yaml`, write realistic requests for this agent's domain:

- 5-10 LLM prompts that exercise happy path, edge cases, multi-step workflows, and likely tool use.
- 3-5 MCP tool calls if a registry exists; tool names and arguments must match the registry schema.
- No generic filler such as "what is 2+2" unless the agent is actually a general Q&A bot.
