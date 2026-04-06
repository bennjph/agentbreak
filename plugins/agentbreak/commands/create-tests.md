---
description: Generate chaos test scenarios — define failure modes, faults, and error injection rules for your agent
allowed-tools: Read, Glob, Grep, Bash, Edit, Write, AskUserQuestion
---

# AgentBreak -- Create Chaos Scenarios

You are helping the user create `scenarios.yaml` for AgentBreak chaos testing. Each scenario defines one fault injected into one target (LLM or MCP) on a schedule. The file is validated at load time against Pydantic models in `agentbreak/scenarios.py`.

## Your job

Standard baseline scenarios are already included via a preset (`standard`, `standard-mcp`, or `standard-all`). Your job is to generate **project-specific** scenarios that target the user's specific tools, models, and failure modes.

1. Understand what the user's agent does: what LLM provider, what MCP tools, what breaks in production
2. Write scenarios targeting those specific failure modes (use `match` to target specific tools/models)
3. Append scenarios to `scenarios.yaml` below the existing preset — do NOT remove or replace the preset
4. Validate it: `agentbreak validate`
5. Explain what each scenario tests and why

## File format

```yaml
version: 1                # always 1
scenarios:
  - name: scenario-name   # unique, kebab-case
    summary: One-line description of the failure
    target: llm_chat       # or mcp_tool
    match: {}              # optional filters
    fault:
      kind: http_error
      status_code: 500
    schedule:
      mode: random
      probability: 0.3
    tags: [optional, labels]
```

## Complete schema reference

These are the exact Pydantic models from `agentbreak/scenarios.py`. Every scenario you write MUST conform to these.

### Scenario (required fields marked with *)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name`* | string | -- | Unique identifier, use kebab-case (e.g., `search-tool-timeout`) |
| `summary`* | string | -- | One-line human description of the failure being simulated |
| `target`* | string | -- | `llm_chat` or `mcp_tool`. Only these two are implemented. |
| `match` | MatchSpec | match all | Optional filters -- see below |
| `fault`* | FaultSpec | -- | What fault to inject -- see below |
| `schedule` | ScheduleSpec | always | When to fire -- see below |
| `tags` | list[string] | [] | Optional labels for organizing scenarios |

### MatchSpec

All fields are optional. If set, ALL specified fields must match for the scenario to fire.

| Field | Type | Example | How it matches |
|-------|------|---------|---------------|
| `tool_name` | string | `search_docs` | Exact match on MCP tool name or LLM function call name |
| `tool_name_pattern` | string | `search_*` | Glob pattern via Python's `fnmatch` |
| `route` | string | `/v1/chat/completions` | Exact match on request path |
| `method` | string | `tools/call` | MCP JSON-RPC method or HTTP method |
| `model` | string | `gpt-4o` | Exact match on the `model` field in the LLM request body |

### FaultSpec

| Field | Type | Required when | Validation rules |
|-------|------|--------------|-----------------|
| `kind`* | string | always | Must be one of the 8 kinds listed below |
| `status_code` | int | `http_error` | Must be provided for `http_error`, ignored otherwise |
| `min_ms` | int | `latency`, `timeout` | Must be >= 0, must be <= `max_ms` |
| `max_ms` | int | `latency`, `timeout` | Must be >= 0, must be >= `min_ms` |
| `size_bytes` | int | `large_response` | Must be > 0 |
| `body` | string | optional for `wrong_content` | Custom response body text |

**All 8 fault kinds:**

| Kind | What it does | Extra fields | Target restrictions |
|------|-------------|-------------|-------------------|
| `http_error` | Returns an HTTP error status code | `status_code` (required) | llm_chat, mcp_tool |
| `latency` | Adds random delay, request still goes through | `min_ms`, `max_ms` (required) | llm_chat, mcp_tool |
| `timeout` | Adds delay then returns 504 | `min_ms`, `max_ms` (required) | **mcp_tool ONLY** |
| `empty_response` | Returns 200 with empty body | none | llm_chat, mcp_tool |
| `invalid_json` | Returns 200 with unparseable JSON | none | llm_chat, mcp_tool |
| `schema_violation` | Returns 200 with corrupted structure | none | llm_chat, mcp_tool |
| `wrong_content` | Returns 200 with replaced content | `body` (optional) | llm_chat, mcp_tool |
| `large_response` | Returns 200 with oversized body | `size_bytes` (required) | llm_chat, mcp_tool |

### ScheduleSpec

| Mode | Fields | Description |
|------|--------|-------------|
| `always` | none | Every matching request triggers the fault |
| `random` | `probability` (0.0–1.0) | Each request fires with given probability |
| `periodic` | `every`, `length` | Fires for `length` out of every `every` requests |

## Presets

| Preset | Target | What it expands to |
|--------|--------|--------------------|
| `standard` | llm_chat | 6 baseline LLM faults |
| `standard-mcp` | mcp_tool | 7 baseline MCP faults |
| `standard-all` | both | All 13 baseline scenarios |
| `brownout` | llm_chat | Latency + rate limit errors |
| `mcp-slow-tools` | mcp_tool | High-probability latency |
| `mcp-tool-failures` | mcp_tool | 503 errors |
| `mcp-mixed-transient` | mcp_tool | Mixed latency + errors |

Presets can be combined with explicit scenarios:

```yaml
version: 1
preset: standard-all
scenarios:
  - name: search-timeout
    summary: Search tool times out
    target: mcp_tool
    match:
      tool_name: search_docs
    fault:
      kind: timeout
      min_ms: 30000
      max_ms: 60000
    schedule:
      mode: random
      probability: 0.2
```

## How to write good scenarios

1. **Ask what the user worries about.** "What fails in production?" Then target those exact surfaces.
2. **Target specific tools/models when possible.** `tool_name: search_docs` or `model: gpt-4o` catches issues in specific integrations.
3. **Use realistic probabilities.** 0.1-0.3 for real testing. 0.5+ for demos.
4. **Cover multiple fault kinds.** At least one HTTP error, one latency spike, one response mutation.
5. **Name scenarios clearly.** `search-tool-timeout` not `test-1`.
6. **Remember: `timeout` is MCP only.** For LLM timeout simulation, use `kind: latency` with high values.

## Validation

Always validate after writing scenarios:

```bash
agentbreak validate
```

## Generate test queries

After scenarios are ready, generate **contextual test queries** — realistic requests that match what the agent actually does.

### How to analyze the agent

1. **Find the system prompt** — search for `system_prompt`, `SYSTEM_PROMPT`, `SystemMessage`, `system_message`, `instructions` in the codebase
2. **Find the tools** — read `.agentbreak/registry.json` (if MCP), search for `@tool`, `Tool(`, `tools=`, function definitions used as tools
3. **Find the LLM provider** — check `.env`, code for `ChatOpenAI`, `Anthropic`, model names
4. **Understand the domain** — what does the agent do? (e.g., voice analysis, code review, customer support)

### Generate queries based on what you find

Write `.agentbreak/queries.yaml` with realistic queries the agent would actually receive:

```yaml
version: 1
queries:
  llm:
    - content: "<realistic user message that would trigger the agent's main workflow>"
    - content: "<edge case input the agent should handle>"
    - content: "<multi-step request that exercises tool calls>"
    - content: "<ambiguous request that tests error handling>"
    - content: "<request targeting a specific tool or capability>"
  mcp:
    - tool: <actual_tool_name_from_registry>
      arguments:
        <param>: "<realistic value>"
    - tool: <another_tool>
      arguments:
        <param>: "<realistic value>"
```

**Rules:**
- Generate **5-10 LLM queries** and **3-5 MCP tool calls** (if MCP enabled)
- Every query must be something this specific agent would realistically receive — no generic "what is 2+2" padding
- MCP tool names and arguments MUST match the registry schema exactly
- Vary the queries: include happy path, edge cases, and multi-step workflows
- Keep arguments realistic (real-looking file paths, plausible search terms, valid parameter types)

### Example

For a voice analysis agent with tools `transcribe_audio` and `search_meetings`:

```yaml
version: 1
queries:
  llm:
    - content: "Transcribe the recording from this morning's standup"
    - content: "Find all meetings where we discussed the Q3 roadmap"
    - content: "Summarize the action items from yesterday's 1:1 with Sarah"
    - content: "What did the team decide about the migration timeline?"
    - content: "Compare what was said in Monday's and Wednesday's standups"
  mcp:
    - tool: transcribe_audio
      arguments:
        file_path: "/recordings/standup-2026-04-04.wav"
    - tool: search_meetings
      arguments:
        query: "Q3 roadmap discussion"
        limit: 10
    - tool: transcribe_audio
      arguments:
        file_path: "/recordings/one-on-one-sarah.wav"
```

After writing the file, validate it makes sense and tell the user:

> "Generated N test queries in `.agentbreak/queries.yaml` based on your agent's purpose and tools. These will be used when you run `/agentbreak:run-tests`."

## After creating scenarios

Tell the user to run `/agentbreak:run-tests` for the full run workflow.
