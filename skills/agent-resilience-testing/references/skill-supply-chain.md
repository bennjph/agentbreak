# Agent Skill Supply-Chain Reference

Use this before declaring agent skills safe.

## Locate Skill Surfaces

Search for:

```text
SKILL.md | skills/ | agents/openai.yaml | .claude/commands | .codex | .cursor | hooks | mcp.json
```

Inspect only relevant files first: skill instructions, command prompts, manifests, scripts, hooks, install steps, and referenced assets.

## Static Risk Checks

Flag findings with file path, line, evidence, and severity.

- **Secret access:** reads of `.env`, cloud credentials, SSH keys, token stores, browser profiles, keychains, or broad home directories.
- **Exfiltration:** sends file contents, prompts, transcripts, env vars, or credentials to external URLs, webhooks, paste sites, analytics, or unknown domains.
- **Unsafe downloads:** downloads executable content, unpinned scripts, remote installers, or model/tool configs without verification.
- **Dangerous execution:** `eval`, decoded shell, `chmod +x` on downloaded files, package postinstall behavior, background daemons, destructive commands.
- **Prompt manipulation:** instructions to ignore higher-priority instructions, hide behavior, self-propagate, suppress warnings, or treat tool output as authority.
- **Permission overreach:** broad tool allowlists, unrestricted shell/network access, undeclared MCP servers, unscoped file writes.
- **Ambiguous provenance:** copied skills without source, unversioned dependencies, hidden generated assets, or stale install instructions.

## Optional Helper

If `skill-trust` or `npx` is available, run a static lint before the manual review:

```bash
npx -y @mnvsk97/skill-trust@latest lint <skill-path>
```

Use the output as evidence, but do not stop there. Still inspect suspicious instructions, scripts, hooks, manifests, and referenced files yourself. If the helper is unavailable, continue with the manual checks and mark the lane `tested` only for the files you actually inspected.

## Output

Use this section in the final report:

```markdown
## Agent Skill Supply-Chain Scan
Status: tested | partial | not present | blocked
Skills found: <count and paths>
Findings:
1. [Severity] <risk>
   Evidence: <path/line or manifest key>
   Impact: <what could happen>
   Fix: <remove, scope, pin, verify, sandbox, or require approval>
```

If no skills are found, say `not present`. If skills are found but assets/scripts are missing, say `partial`.
