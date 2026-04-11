# Roadmap

## Shipped

- **MCP security testing** — tool poisoning, rug pull attacks, and tool call validation are implemented. Adversarial inputs injected via MCP tool responses, prompt injection and data exfiltration testing are live.

## Planned Features

- **Pattern-based attacks** — multi-step attack chains that exploit common agent reasoning patterns
- **Skill-based attacks** — target agent skills/capabilities with adversarial tool sequences
- **Deprecated library injection** — return responses referencing deprecated or vulnerable libraries
- **Model deprecation simulation** — simulate model sunset responses and version migration failures

## Deferred Scenario Targets

Scenario targets that are recognized by the schema but not yet implemented.

### `queue`
- Duplicate delivery
- Delayed delivery
- Lost acknowledgement

### `state`
- Checkpoint corruption
- Stale checkpoint resume

### `memory`
- Poisoned memory
- Cross-tenant memory leakage
- Stale memory retrieval

### `artifact_store`
- Missing artifact
- Zero-byte artifact
- Stale artifact version

### `approval`
- Stale approval replay
- Expired approval token

### `browser_worker`
- Session expiry
- Wrong-window interaction
- DOM drift

### `multi_agent`
- Delegation cascade
- Shared-state corruption

### `telemetry`
- Missing span
- Missing tool result audit trail
