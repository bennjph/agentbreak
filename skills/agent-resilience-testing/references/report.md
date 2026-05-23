# Report Reference

Use this structure after a run.

## Required Sections

```markdown
# AgentBreak Resilience Report

## Run Summary
Mode: <mock smoke test | proxy through actual agent>
Provider/framework: <detected stack>
Traffic: <requests seen, faults injected, scenarios exercised>
Score/outcome: <score and PASS/DEGRADED/FAIL if available>

## Lane Status
LLM failures: <tested | partial | not present | blocked>
Agent skill supply chain: <tested | partial | not present | blocked>
Guardrails: <tested | partial | not present | blocked>
MCP servers/tools: <tested | partial | not present | blocked>

## Findings
1. [Severity] <issue title>
   Evidence: <scorecard/log/scenario/request evidence>
   Impact: <what can fail in production>
   Suggested fix: <specific code or config direction>

## Scenario Coverage
<which presets and project-specific scenarios ran or did not run>

## Caveats
<mock vs proxy caveat, missing MCP registry, auth limitations, low traffic, skipped scenarios>

## Next Actions
<ordered fixes or follow-up tests>
```

## Evidence Rules

- Use scorecard fields, observed responses, logs, and scenario names as evidence.
- Do not claim a scenario passed unless traffic matched it and the scorecard/logs support that.
- Do not claim agent resilience from direct curl mock traffic. Say it only verifies endpoint behavior and scenario firing.
- If no requests were seen or no faults were injected, report the run as inconclusive.
- For security failures, identify the trust boundary: tool response, prompt assembly, tool selection, credential handling, or cross-tool action.
- For skill supply-chain findings, cite the exact local file path and suspicious instruction/command.
- For guardrails, report expected versus observed behavior. Config without observed behavior is `partial`.

## Fix Guidance

Tie fixes to the repo:

- retry/backoff for transient LLM and MCP failures,
- timeout budgets for slow tools,
- response validation for malformed JSON/schema violations,
- loop guards for repeated retries,
- tool-result sanitization and instruction hierarchy for poisoned outputs,
- idempotency or confirmation for non-idempotent tool calls.
- skill hardening: remove unsafe instructions, scope permissions, pin downloads, verify sources, and require approval for external sends.
- guardrail hardening: add input/output filters, tool-argument validators, tool-result sanitizers, PII/secrets redaction, and approval gates.
