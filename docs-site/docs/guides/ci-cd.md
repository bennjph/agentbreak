# CI/CD Integration

Run chaos tests in your pipeline to catch resilience regressions before they hit production.

## Mock mode (no API keys)

The simplest setup — AgentBreak generates synthetic responses, so no secrets are needed.

### GitHub Actions

```yaml
name: Chaos Test

on:
  push:
    branches: [main]
  pull_request:

jobs:
  chaos-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - name: Install
        run: pip install agentbreak

      - name: Start proxy
        run: |
          agentbreak init
          agentbreak serve &
          sleep 2
          curl -s http://localhost:5005/healthz

      - name: Send test traffic
        run: |
          for i in $(seq 1 10); do
            curl -s http://localhost:5005/v1/chat/completions \
              -H "Content-Type: application/json" \
              -H "Authorization: Bearer dummy" \
              -d "{\"model\":\"gpt-4o\",\"messages\":[{\"role\":\"user\",\"content\":\"test $i\"}]}" &
          done
          wait

      - name: Check resilience score
        run: |
          SCORE=$(curl -s http://localhost:5005/_agentbreak/scorecard | python3 -c "import sys,json; print(json.load(sys.stdin)['score'])")
          echo "Resilience score: $SCORE"
          pkill -f "agentbreak serve" || true
          python3 -c "exit(0 if $SCORE >= 60 else 1)"
```

### GitLab CI

```yaml
chaos-test:
  image: python:3.12
  script:
    - pip install agentbreak
    - agentbreak init
    - agentbreak serve &
    - sleep 2
    - |
      for i in $(seq 1 10); do
        curl -s http://localhost:5005/v1/chat/completions \
          -H "Content-Type: application/json" \
          -H "Authorization: Bearer dummy" \
          -d "{\"model\":\"gpt-4o\",\"messages\":[{\"role\":\"user\",\"content\":\"test $i\"}]}" &
      done
      wait
    - |
      SCORE=$(curl -s http://localhost:5005/_agentbreak/scorecard | python3 -c "import sys,json; print(json.load(sys.stdin)['score'])")
      echo "Resilience score: $SCORE"
      pkill -f "agentbreak serve" || true
      python3 -c "exit(0 if $SCORE >= 60 else 1)"
```

## Proxy mode (real API traffic)

For testing through your actual agent with real LLM calls, set your API key as a CI secret.

### GitHub Actions

```yaml
- name: Start proxy (proxy mode)
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: |
    agentbreak serve &
    sleep 2
```

Make sure `.agentbreak/application.yaml` has `mode: proxy` and the correct `upstream_url`.

## Custom scenarios

Commit `.agentbreak/application.yaml` and `.agentbreak/scenarios.yaml` to your repo so CI uses the same config as local development.

```yaml
# .agentbreak/scenarios.yaml
preset: standard
```

Or use a specific preset for CI:

```yaml
preset: brownout
```

## Setting a score threshold

The scorecard returns a 0-100 score. Pick a threshold that makes sense for your agent:

| Threshold | When to use |
|-----------|-------------|
| `>= 80` | Strict — agent must handle most faults gracefully |
| `>= 60` | Moderate — allows some degradation under chaos |
| `>= 40` | Lenient — just checking the agent doesn't crash |

## Tips

- **Start with mock mode** — no secrets, fast, good for catching basic issues
- **Use `preset: standard`** for a balanced set of faults
- **Commit your `.agentbreak/` configs** so everyone runs the same scenarios
- **Run on PRs** to catch regressions before merge
- **Compare runs** with `agentbreak history` if you enable history tracking
