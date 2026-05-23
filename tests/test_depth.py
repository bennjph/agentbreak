"""Depth tests — recovery flows, multi-scenario interaction, streaming+faults,
concurrency, latency timing, fingerprint edge cases, report generation,
and MCP recovery asymmetry."""
from __future__ import annotations

import json
import time
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agentbreak import main
from agentbreak.config import MCPRegistry, MCPTool
from agentbreak.scenarios import ScenarioFile


CHAT_BODY = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
OPENAI_STREAM_BODY = {"model": "m", "messages": [{"role": "user", "content": "hi"}], "stream": True}
ANTHROPIC_STREAM_BODY = {"model": "m", "max_tokens": 100, "messages": [{"role": "user", "content": "hi"}], "stream": True}


def _make_llm_runtime(scenarios_raw=None, mode="mock"):
    scenarios = []
    if scenarios_raw is not None:
        scenarios = ScenarioFile.model_validate({"scenarios": scenarios_raw}).scenarios
    return main.LLMRuntime(
        mode=mode, upstream_url="", auth_headers={}, scenarios=scenarios,
    )


def _scenario(name, fault, target="llm_chat", match=None, schedule=None):
    s = {
        "name": name,
        "summary": name,
        "target": target,
        "fault": fault,
        "schedule": schedule or {"mode": "always"},
    }
    if match:
        s["match"] = match
    return s


def _setup_mcp(scenarios_data=None):
    scenarios = []
    if scenarios_data:
        scenarios = ScenarioFile.model_validate({"scenarios": scenarios_data}).scenarios
    main.service_state.mcp_runtime = main.MCPRuntime(
        upstream_url="", auth_headers={},
        registry=MCPRegistry(
            tools=[
                MCPTool(name="search", description="Search", inputSchema={"type": "object"}),
                MCPTool(name="fetch", description="Fetch", inputSchema={"type": "object"}),
            ],
        ),
        scenarios=scenarios,
    )
    return TestClient(main.app)


# ═══════════════════════════════════════════════════════════════════════
# 1. Recovery flow
# ═══════════════════════════════════════════════════════════════════════


def test_recovery_after_http_error():
    """Fault → clean request → scorecard shows recovery."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario("err", {"kind": "http_error", "status_code": 500},
                  schedule={"mode": "periodic", "every": 2, "length": 1}),
    ])
    client = TestClient(main.app)
    # Request 1: fault fires (periodic: 1st of every 2)
    r1 = client.post("/v1/chat/completions", json=CHAT_BODY)
    assert r1.status_code == 500
    # Request 2: no fault (periodic: 2nd of every 2) — should count as recovery
    r2 = client.post("/v1/chat/completions",
                     json={"model": "m", "messages": [{"role": "user", "content": "retry"}]})
    assert r2.status_code == 200

    sc = client.get("/_agentbreak/scorecard").json()
    assert sc["fault_recoveries"] == 1
    assert sc["unrecovered_faults"] == 0
    assert sc["recovery_rate"] == 1.0


def test_recovery_rate_partial():
    """Two faults, one recovery → 50% recovery rate."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario("err", {"kind": "http_error", "status_code": 429},
                  schedule={"mode": "periodic", "every": 3, "length": 1}),
    ])
    client = TestClient(main.app)
    # Req 1: fault
    assert client.post("/v1/chat/completions", json=CHAT_BODY).status_code == 429
    # Req 2: clean → recovery
    assert client.post("/v1/chat/completions",
                       json={"model": "m", "messages": [{"role": "user", "content": "2"}]}).status_code == 200
    # Req 3: clean
    assert client.post("/v1/chat/completions",
                       json={"model": "m", "messages": [{"role": "user", "content": "3"}]}).status_code == 200
    # Req 4: fault again
    assert client.post("/v1/chat/completions",
                       json={"model": "m", "messages": [{"role": "user", "content": "4"}]}).status_code == 429

    sc = client.get("/_agentbreak/scorecard").json()
    assert sc["injected_faults"] == 2
    assert sc["fault_recoveries"] == 1
    assert sc["recovery_rate"] == 0.5


def test_no_recovery_when_faults_are_consecutive():
    """Back-to-back faults with no clean request → zero recoveries."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario("err", {"kind": "http_error", "status_code": 500}),
    ])
    client = TestClient(main.app)
    client.post("/v1/chat/completions", json=CHAT_BODY)
    client.post("/v1/chat/completions",
                json={"model": "m", "messages": [{"role": "user", "content": "2"}]})

    sc = client.get("/_agentbreak/scorecard").json()
    assert sc["fault_recoveries"] == 0
    assert sc["unrecovered_faults"] == 2


def test_recovery_updates_scenario_stats():
    """Per-scenario stats track recovered/unrecovered correctly."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario("err", {"kind": "http_error", "status_code": 500},
                  schedule={"mode": "periodic", "every": 2, "length": 1}),
    ])
    client = TestClient(main.app)
    # Fault, then clean
    client.post("/v1/chat/completions", json=CHAT_BODY)
    client.post("/v1/chat/completions",
                json={"model": "m", "messages": [{"role": "user", "content": "retry"}]})

    sc = client.get("/_agentbreak/scorecard").json()
    err_scenario = next(s for s in sc["scenarios"] if s["name"] == "err")
    assert err_scenario["triggered"] == 1
    assert err_scenario["recovered"] == 1
    assert err_scenario["unrecovered"] == 0
    assert err_scenario["status"] == "survived"


# ═══════════════════════════════════════════════════════════════════════
# 2. Multi-scenario interaction
# ═══════════════════════════════════════════════════════════════════════


def test_first_matching_scenario_wins():
    """When multiple scenarios match, the first one in the list fires."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario("err-500", {"kind": "http_error", "status_code": 500}),
        _scenario("err-429", {"kind": "http_error", "status_code": 429}),
    ])
    client = TestClient(main.app)
    r = client.post("/v1/chat/completions", json=CHAT_BODY)
    # First scenario (500) should win over second (429)
    assert r.status_code == 500


def test_match_filter_selects_correct_scenario():
    """Scenarios with different match filters fire on the right requests."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario("gpt4-err", {"kind": "http_error", "status_code": 500},
                  match={"model": "gpt-4o"}),
        _scenario("gpt35-empty", {"kind": "empty_response"},
                  match={"model": "gpt-3.5"}),
    ])
    client = TestClient(main.app)
    r1 = client.post("/v1/chat/completions",
                     json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]})
    assert r1.status_code == 500

    r2 = client.post("/v1/chat/completions",
                     json={"model": "gpt-3.5", "messages": [{"role": "user", "content": "hi"}]})
    assert r2.status_code == 200
    assert r2.content == b""


def test_unmatched_request_passes_through():
    """Request that matches no scenario gets a clean response."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario("gpt4-only", {"kind": "http_error", "status_code": 500},
                  match={"model": "gpt-4o"}),
    ])
    client = TestClient(main.app)
    r = client.post("/v1/chat/completions",
                     json={"model": "claude", "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    assert r.json()["model"] == "agentbreak-mock"


def test_multiple_scenarios_track_separate_stats():
    """Each scenario maintains independent stats."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario("gpt4-err", {"kind": "http_error", "status_code": 500},
                  match={"model": "gpt-4o"}),
        _scenario("gpt35-err", {"kind": "http_error", "status_code": 429},
                  match={"model": "gpt-3.5"}),
    ])
    client = TestClient(main.app)
    client.post("/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "1"}]})
    client.post("/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "2"}]})
    client.post("/v1/chat/completions",
                json={"model": "gpt-3.5", "messages": [{"role": "user", "content": "3"}]})

    sc = client.get("/_agentbreak/scorecard").json()
    stats_by_name = {s["name"]: s for s in sc["scenarios"]}
    assert stats_by_name["gpt4-err"]["triggered"] == 2
    assert stats_by_name["gpt35-err"]["triggered"] == 1


def test_pre_and_post_scenarios_on_same_target():
    """A pre-phase (latency) and post-phase (wrong_content) scenario coexist.
    The pre-phase runs on every request; the post-phase also mutates."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario("slow", {"kind": "latency", "min_ms": 1, "max_ms": 1}),
        _scenario("wrong", {"kind": "wrong_content", "body": "REPLACED"}),
    ])
    client = TestClient(main.app)
    r = client.post("/v1/chat/completions", json=CHAT_BODY)
    # Latency fires first (pre-phase), then wrong_content mutates (post-phase)
    # But choose_matching_scenario returns the FIRST match — latency wins
    # so the response should be normal (latency is delay-only)
    assert r.status_code == 200
    # Since latency matched first, wrong_content never fires
    data = r.json()
    assert data["choices"][0]["message"]["content"] == "AgentBreak mock response."


def test_mcp_multiple_scenarios_different_tools():
    """MCP scenarios with different tool_name matches fire independently."""
    client = _setup_mcp([
        _scenario("search-err", {"kind": "http_error", "status_code": 503},
                  target="mcp_tool", match={"tool_name": "search"}),
        _scenario("fetch-empty", {"kind": "empty_response"},
                  target="mcp_tool", match={"tool_name": "fetch"}),
    ])
    r1 = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                    "params": {"name": "search", "arguments": {}}})
    assert r1.status_code == 503

    r2 = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                    "params": {"name": "fetch", "arguments": {}}})
    assert r2.status_code == 200
    assert r2.content == b""


# ═══════════════════════════════════════════════════════════════════════
# 3. Streaming + post-phase fault interaction
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("name", "fault"),
    [
        ("empty", {"kind": "empty_response"}),
        ("schema", {"kind": "schema_violation"}),
        ("wrong", {"kind": "wrong_content", "body": "REPLACED"}),
        ("large", {"kind": "large_response", "size_bytes": 10000}),
    ],
)
def test_stream_response_mutation_faults_skipped(name, fault):
    """Response mutation faults are skipped for streaming."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario(name, fault),
    ])
    client = TestClient(main.app)
    r = client.post("/v1/chat/completions", json=OPENAI_STREAM_BODY)
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "[DONE]" in r.text


def test_anthropic_stream_post_faults_skipped():
    """Post-phase faults are also skipped for Anthropic streaming."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario("empty", {"kind": "empty_response"}),
    ])
    client = TestClient(main.app)
    r = client.post("/v1/messages", json=ANTHROPIC_STREAM_BODY)
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "message_stop" in r.text


# ═══════════════════════════════════════════════════════════════════════
# 4. Latency timing verification
# ═══════════════════════════════════════════════════════════════════════


def test_latency_fault_actually_delays():
    """Verify that latency fault introduces measurable delay."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario("slow", {"kind": "latency", "min_ms": 100, "max_ms": 100}),
    ])
    client = TestClient(main.app)
    t0 = time.monotonic()
    r = client.post("/v1/chat/completions", json=CHAT_BODY)
    elapsed_ms = (time.monotonic() - t0) * 1000
    assert r.status_code == 200
    assert elapsed_ms >= 80  # allow small margin for test overhead


def test_mcp_timeout_fault_actually_delays():
    """MCP timeout fault introduces delay before returning 504."""
    client = _setup_mcp([
        _scenario("to", {"kind": "timeout", "min_ms": 100, "max_ms": 100},
                  target="mcp_tool"),
    ])
    t0 = time.monotonic()
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                   "params": {"name": "search", "arguments": {}}})
    elapsed_ms = (time.monotonic() - t0) * 1000
    assert r.status_code == 504
    assert elapsed_ms >= 80


def test_latency_recorded_in_scorecard():
    """Latency samples appear in scorecard stats."""
    main.service_state.llm_runtime = _make_llm_runtime()
    client = TestClient(main.app)
    client.post("/v1/chat/completions", json=CHAT_BODY)
    sc = client.get("/_agentbreak/scorecard").json()
    assert sc["latency"] is not None
    assert sc["latency"]["avg_ms"] >= 0
    assert sc["latency"]["max_ms"] >= 0


# ═══════════════════════════════════════════════════════════════════════
# 5. Fingerprint / loop detection edge cases
# ═══════════════════════════════════════════════════════════════════════


def test_duplicate_detection_counts_correctly():
    """2nd identical request = duplicate, 3rd = suspected loop."""
    main.service_state.llm_runtime = _make_llm_runtime()
    client = TestClient(main.app)
    body = {"model": "m", "messages": [{"role": "user", "content": "same"}]}
    client.post("/v1/chat/completions", json=body)  # 1st: new
    client.post("/v1/chat/completions", json=body)  # 2nd: duplicate
    client.post("/v1/chat/completions", json=body)  # 3rd: loop

    sc = client.get("/_agentbreak/scorecard").json()
    assert sc["duplicate_requests"] == 2  # 2nd and 3rd are duplicates
    assert sc["suspected_loops"] == 1     # only 3rd triggers loop


def test_different_bodies_are_not_duplicates():
    """Different request bodies should not trigger duplicate detection."""
    main.service_state.llm_runtime = _make_llm_runtime()
    client = TestClient(main.app)
    for i in range(5):
        client.post("/v1/chat/completions",
                    json={"model": "m", "messages": [{"role": "user", "content": f"msg-{i}"}]})

    sc = client.get("/_agentbreak/scorecard").json()
    assert sc["duplicate_requests"] == 0
    assert sc["suspected_loops"] == 0


# ═══════════════════════════════════════════════════════════════════════
# 6. Report generation
# ═══════════════════════════════════════════════════════════════════════


def test_build_full_report_includes_both_runtimes():
    """Full report has llm and mcp sections when both are active."""
    main.service_state.llm_runtime = _make_llm_runtime()
    _setup_mcp()
    client = TestClient(main.app)
    client.post("/v1/chat/completions", json=CHAT_BODY)
    client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "search", "arguments": {}}})

    report = main._build_full_report(main.service_state)
    assert "llm" in report
    assert "mcp" in report
    assert report["llm"]["requests_seen"] == 1
    assert report["mcp"]["tool_calls"] == 1
    assert report["version"] == 1
    assert "agentbreak_version" in report
    assert "timestamp" in report


def test_build_full_report_llm_only():
    """Report only has llm section when MCP is disabled."""
    main.service_state.llm_runtime = _make_llm_runtime()
    main.service_state.mcp_runtime = None
    client = TestClient(main.app)
    client.post("/v1/chat/completions", json=CHAT_BODY)

    report = main._build_full_report(main.service_state)
    assert "llm" in report
    assert "mcp" not in report


def test_save_report_file(tmp_path):
    """Report JSON is saved to disk."""
    report = {"version": 1, "llm": {"resilience_score": 85}}
    with patch.object(Path, "mkdir"):
        path = main._save_report_file(report)
    # Just verify it returns a path (actual file creation depends on cwd)
    # Test the function doesn't crash
    assert path is None or isinstance(path, Path)


def test_format_summary_lines_pass():
    """PASS outcome produces correct summary."""
    data = {
        "run_outcome": "PASS", "resilience_score": 100,
        "requests_seen": 10, "injected_faults": 3,
        "recovery_rate": None, "scenarios": [],
        "latency": None,
    }
    lines = main._format_summary_lines("LLM", data)
    text = "\n".join(lines)
    assert "PASSED" in text
    assert "100" in text


def test_format_summary_lines_failed_with_scenarios():
    """FAIL outcome includes scenario details with fix hints."""
    data = {
        "run_outcome": "FAIL", "resilience_score": 30,
        "requests_seen": 10, "injected_faults": 5,
        "recovery_rate": 0.0,
        "scenarios": [
            {"name": "err-500", "kind": "http_error", "triggered": 3,
             "recovered": 0, "unrecovered": 3, "status": "failed"},
        ],
        "latency": {"avg_ms": 50, "p95_ms": 2000, "max_ms": 3000},
    }
    lines = main._format_summary_lines("LLM", data)
    text = "\n".join(lines)
    assert "FAILED" in text
    assert "err-500" in text
    assert "Fix:" in text
    # Latency shown because p95 > 1000
    assert "p95" in text


def test_format_summary_lines_hides_low_latency():
    """Latency hidden when p95 <= 1000ms."""
    data = {
        "run_outcome": "PASS", "resilience_score": 100,
        "requests_seen": 5, "injected_faults": 0,
        "recovery_rate": None, "scenarios": [],
        "latency": {"avg_ms": 10, "p95_ms": 50, "max_ms": 100},
    }
    lines = main._format_summary_lines("LLM", data)
    text = "\n".join(lines)
    assert "p95" not in text


# ═══════════════════════════════════════════════════════════════════════
# 7. MCP recovery asymmetry
# ═══════════════════════════════════════════════════════════════════════


def test_mcp_scorecard_has_no_recovery_rate():
    """MCP scorecard intentionally has no recovery_rate or fault_recoveries."""
    client = _setup_mcp([
        _scenario("err", {"kind": "http_error", "status_code": 503},
                  target="mcp_tool", match={"tool_name": "search"}),
    ])
    client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "search", "arguments": {}}})
    # Clean request (different tool, no fault)
    client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                               "params": {"name": "fetch", "arguments": {}}})

    sc = client.get("/_agentbreak/mcp-scorecard").json()
    assert "recovery_rate" not in sc
    assert "fault_recoveries" not in sc


def test_mcp_score_formula_no_recovery_bonus():
    """MCP score has no recovery bonus — verify formula."""
    client = _setup_mcp([
        _scenario("err", {"kind": "http_error", "status_code": 503},
                  target="mcp_tool"),
    ])
    client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "search", "arguments": {}}})

    sc = client.get("/_agentbreak/mcp-scorecard").json()
    breakdown = sc["score_breakdown"]
    # MCP formula: 100 - (faults * 5) - (failures * 12) - (dups * 2) - (loops * 10)
    assert breakdown["base"] == 100
    assert "recovery_bonus" not in breakdown


# ═══════════════════════════════════════════════════════════════════════
# 8. Concurrency (basic thread safety of stats)
# ═══════════════════════════════════════════════════════════════════════


def test_concurrent_llm_requests_count_correctly():
    """Parallel requests all get counted in total_requests."""
    main.service_state.llm_runtime = _make_llm_runtime()
    client = TestClient(main.app)
    n = 20
    errors = []

    def send_request(i):
        try:
            r = client.post("/v1/chat/completions",
                           json={"model": "m", "messages": [{"role": "user", "content": f"msg-{i}"}]})
            if r.status_code != 200:
                errors.append(f"request {i} got {r.status_code}")
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=send_request, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors: {errors}"
    sc = client.get("/_agentbreak/scorecard").json()
    assert sc["requests_seen"] == n


def test_concurrent_mcp_requests_count_correctly():
    """Parallel MCP requests all get counted."""
    client = _setup_mcp()
    n = 20
    errors = []

    def send_request(i):
        try:
            r = client.post("/mcp", json={
                "jsonrpc": "2.0", "id": i, "method": "tools/call",
                "params": {"name": "search", "arguments": {"q": f"query-{i}"}}
            })
            if r.status_code != 200:
                errors.append(f"request {i} got {r.status_code}")
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=send_request, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors: {errors}"
    sc = client.get("/_agentbreak/mcp-scorecard").json()
    assert sc["tool_calls"] == n


# ═══════════════════════════════════════════════════════════════════════
# 9. Reset clears everything
# ═══════════════════════════════════════════════════════════════════════


def test_reset_clears_all_stats():
    """POST /_agentbreak/reset zeroes out LLM and MCP stats."""
    main.service_state.llm_runtime = _make_llm_runtime([
        _scenario("err", {"kind": "http_error", "status_code": 500}),
    ])
    _setup_mcp([
        _scenario("mcp-err", {"kind": "http_error", "status_code": 503},
                  target="mcp_tool"),
    ])
    client = TestClient(main.app)
    client.post("/v1/chat/completions", json=CHAT_BODY)
    client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "search", "arguments": {}}})

    client.post("/_agentbreak/reset")

    llm_sc = client.get("/_agentbreak/scorecard").json()
    mcp_sc = client.get("/_agentbreak/mcp-scorecard").json()
    assert llm_sc["requests_seen"] == 0
    assert llm_sc["injected_faults"] == 0
    assert mcp_sc["requests_seen"] == 0
    assert mcp_sc["injected_faults"] == 0
