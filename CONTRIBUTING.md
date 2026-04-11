# Contributing

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'   # includes pytest; use '.' for core only
```

## Commands

```bash
agentbreak init                    # create .agentbreak/ config
agentbreak verify                  # run pytest
agentbreak validate                # check config
agentbreak inspect                 # discover MCP tools
agentbreak serve                   # start proxy
```

## Repo Layout

| Path | Role |
|------|------|
| `agentbreak/main.py` | CLI (`serve`, `validate`, `inspect`, `verify`), FastAPI app, proxy logic |
| `agentbreak/config.py` | `application.yaml` Pydantic models, registry I/O |
| `agentbreak/scenarios.py` | `scenarios.yaml` schema and validation |
| `agentbreak/behaviors.py` | Response mutation helpers |
| `agentbreak/faults/catalog/` | Fault definitions (manifest.yaml + optional payloads per fault) |
| `agentbreak/discovery/mcp.py` | MCP server inspection |
| `tests/` | Pytest suite (`agentbreak verify` runs these) |

## Adding a new fault

Each fault lives in `agentbreak/faults/catalog/{category}/{fault_id}/`. To add one:

1. Create the folder: `mkdir -p agentbreak/faults/catalog/security/my_new_fault`
2. Write `manifest.yaml`:
   ```yaml
   id: my_new_fault
   name: My New Fault
   category: security
   severity: high
   targets: [mcp_tool]
   tags: [security, my-tag]

   description: "What happens when this fault fires"
   fix_hint: "How the agent should handle it"

   phase: post          # pre (before upstream) or post (mutate response)
   action: inject_text  # one of: delay, return_error, replace_body, inject_text, corrupt_json, corrupt_schema, large_body, wrong_content
   params:
     position: append
     payload_dir: payloads/

   required_fields: [poison_type]
   ```
3. Add payload files if needed: `payloads/variant_name.txt`
4. Run `agentbreak verify` to confirm tests pass

The fault is auto-discovered — no imports or registration needed.

For complex faults that need custom logic, add a `handler.py` with `phase: custom` in the manifest. See `catalog/security/rug_pull/` for an example.

## Guidelines

- Keep the product surface small.
- Prefer one clear path over several aliases or modes.
- Keep scenarios explicit and typed.
- Preserve test isolation so `agentbreak verify` stays deterministic.
- Update docs when config shape or fault types change.

Full docs at [mnvsk97.github.io/agentbreak](https://mnvsk97.github.io/agentbreak).
