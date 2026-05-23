# Detection Reference

Use this when analyzing a target codebase before configuring AgentBreak.

## What To Identify

- **Provider:** OpenAI, Anthropic, OpenAI-compatible gateway, or custom proxy.
- **Framework:** LangGraph, LangChain, CrewAI, AutoGen, raw SDK, MCP client, or custom orchestration.
- **Connection points:** base URL env vars, SDK constructors, config files, MCP server URLs, and `.env` usage.
- **Agent skills/capabilities:** local `SKILL.md` files, command prompts, skill metadata, hooks, MCP config, and tool permissions.
- **Tools:** MCP tools, function/tool calls, retrieval tools, browser/file tools, external service wrappers, and non-idempotent actions.
- **Guardrails:** input filters, output filters, PII/secrets redaction, tool-argument validators, approval gates, and policy middleware.
- **Failure handling:** retries, backoff, timeouts, circuit breakers, fallback models, exception handling, loop guards, and user-facing error messages.
- **Risk areas:** non-idempotent tools, secret-bearing tool outputs, prompt assembly, tool-result trust boundaries, long-running workflows, and multi-agent handoffs.

## Useful Searches

Run targeted searches for these families:

```text
openai | anthropic | OPENAI_API_KEY | ANTHROPIC_API_KEY | base_url | api_base
langgraph | langchain | crewai | autogen | mcp | MCPClient | tools= | tool_call
retry | max_retries | backoff | timeout | except | try: | RateLimit | APIError
system_prompt | instructions | SystemMessage | prompt | guardrail
SKILL.md | skills/ | .claude | .codex | .cursor | agents/openai.yaml | hooks | mcp.json
policy | moderation | pii | redact | approval | validate | block | deny
curl | wget | webhook | upload | eval | base64 | chmod | subprocess | shell
```

Check `.env`, `.env.example`, `pyproject.toml`, `package.json`, framework config, deployment config, and app entrypoints. Do not print secrets.

## Findings Format

Before editing AgentBreak config, summarize:

```markdown
Provider: <detected provider or ambiguous candidates>
Framework: <framework/runtime>
MCP/tools: <detected, not detected, or unknown>
Agent skills: <paths/count or not present>
Guardrails: <detected controls or not present>
Error handling: <retry/timeout/fallback observations>
Recommended mode: <mock or proxy, with why>
Open questions: <only blockers that cannot be discovered>
```

## Mode Selection

- **Mock mode:** use for demos, CI, onboarding, and verifying that scenarios fire. It does not exercise the real agent unless the user's agent itself is routed to the mock proxy.
- **Proxy mode:** use for the strongest signal. It exercises real SDK/framework retries, error handling, and tool behavior.
- **MCP enabled:** inspect tools before tests. A missing registry means scenario targeting and tool-call probes are weaker.
