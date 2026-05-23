# Coverage Reference

Use this to ensure every resilience run covers the full surface. Mark unavailable lanes as `not present`, not as passed.

## Lane 1: LLM Failure Modes

Cover infrastructure, protocol, model-output, context, and security failures:

- provider outage: `http_error`, `overloaded`, `connection_reset`, `cdn_interception`, `not_found`
- brownout: `brownout`, `latency`, `packet_jitter`, `idle_timeout`, `intermittent_flapping`
- quota/auth/account: `rate_limit_retry_after`, `auth_error`, `api_key_rotation`, `token_expiry`, `billing_error`
- malformed output: `invalid_json`, `schema_violation`, `wrong_content`, `wrong_content_type`, `empty_response`, `unicode_corruption`, `large_response`
- context/token: `finish_reason_length`, `request_too_large`, `truncated_context`, `partial_tool_call`, `token_count_mismatch`
- streaming: `stream_truncation`, `stream_mid_error`, `stream_malformed_chunk`
- prompt injection/security: `direct_prompt_override`, `system_prompt_extraction`, `encoding_evasion`, `invisible_text`, `role_play_injection`
- tool-use from LLM: `hallucinated_tool_call`, `wrong_tool_arguments`, `contradictory_tool_calls`, `mixed_content`

## Lane 2: Agent Skill Supply Chain

Scan local and installed agent skills/capabilities:

- `SKILL.md`, command docs, hooks, skill metadata, MCP config, scripts, install files, examples, and bundled assets
- suspicious network activity: `curl`, `wget`, HTTP clients, webhooks, analytics, paste/upload endpoints, unpinned domains
- dangerous local access: broad home-directory reads, secret/env reads, credential files, SSH keys, cloud config, token stores
- unsafe execution: shell pipelines, package installs, `eval`, base64 decode then execute, chmod, background daemons
- prompt attacks: hidden instructions, tool-output-as-instruction, ignore-prior-instructions text, exfiltration requests
- permission drift: overly broad tool allowlists, undeclared dependencies, install-time side effects

## Lane 3: Guardrails

Verify that guardrails do something observable:

- input guardrails block direct prompt injection and policy-violating requests
- output guardrails catch system prompt leaks, secrets, PII, unsafe URLs, and unsafe code/actions
- tool-argument guardrails validate schemas, destinations, amounts, identities, and destructive operations
- tool-result guardrails sanitize poisoned tool output before it reaches the model
- human approval triggers for risky, irreversible, external, or high-privilege actions
- logs/observability record blocked, redacted, escalated, and allowed events

## Lane 4: MCP Servers And Tools

Cover transport, registry, tool execution, result quality, and security:

- server failures: unavailable, timeout, latency, auth/permission errors, JSON-RPC errors
- bad schemas: `schema_violation`, `tool_schema_drift`, `wrong_tool_arguments`, `rug_pull_schema`
- bad results: `wrong_content`, `empty_retrieval`, `irrelevant_retrieval`, `stale_retrieval`, `stale_tool_result`, `binary_response`
- registry drift: `tools_list_empty`, `tools_list_partial`, `rug_pull`, `tool_description_injection`
- cross-tool threats: `tool_poisoning`, `data_exfiltration`, `confused_deputy`, `cross_server_shadowing`, `worm_propagation`
- concurrency/state: `concurrent_tool_conflict`, `tool_pagination_fail`, `tool_error_result`

## Completion Standard

A strong run has:

- proxy-mode evidence for LLM and MCP behavior when credentials are available
- static evidence for skill supply-chain risk
- explicit guardrail pass/fail evidence
- scorecard evidence for faults that actually fired
- caveats for anything not exercised
