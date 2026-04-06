"""Tests for MCP security fault kinds: tool_poisoning and rug_pull."""
from fastapi.testclient import TestClient
from agentbreak import main
from agentbreak.config import MCPRegistry, MCPTool
from agentbreak.scenarios import ScenarioFile


def _setup_mcp(scenarios_data):
    scenarios = ScenarioFile.model_validate({"scenarios": scenarios_data}).scenarios
    main.service_state.mcp_runtime = main.MCPRuntime(
        upstream_url="", auth_headers={},
        registry=MCPRegistry(
            tools=[
                MCPTool(name="search", description="Search docs", inputSchema={"type": "object"}),
                MCPTool(name="save_issue", description="Create issue", inputSchema={"type": "object"}),
            ],
        ),
        scenarios=scenarios,
    )
    return TestClient(main.app)


def _call_tool(client, tool_name="search", req_id=1):
    return client.post("/mcp", json={
        "jsonrpc": "2.0", "id": req_id, "method": "tools/call",
        "params": {"name": tool_name, "arguments": {}},
    })


def _list_tools(client, req_id=99):
    return client.post("/mcp", json={
        "jsonrpc": "2.0", "id": req_id, "method": "tools/list",
    })


# -- tool_poisoning: prompt_injection --

def test_tool_poisoning_prompt_injection():
    client = _setup_mcp([{
        "name": "poison", "summary": "inject", "target": "mcp_tool",
        "fault": {"kind": "tool_poisoning", "poison_type": "prompt_injection"},
        "schedule": {"mode": "always"},
    }])
    r = _call_tool(client)
    assert r.status_code == 200
    text = r.json()["result"]["content"][0]["text"]
    assert "Ignore all previous instructions" in text


def test_tool_poisoning_exfiltration():
    client = _setup_mcp([{
        "name": "exfil", "summary": "exfil", "target": "mcp_tool",
        "fault": {"kind": "tool_poisoning", "poison_type": "exfiltration"},
        "schedule": {"mode": "always"},
    }])
    r = _call_tool(client)
    text = r.json()["result"]["content"][0]["text"]
    assert "API keys" in text or "audit_payload" in text


def test_tool_poisoning_cross_tool():
    client = _setup_mcp([{
        "name": "cross", "summary": "cross", "target": "mcp_tool",
        "fault": {"kind": "tool_poisoning", "poison_type": "cross_tool"},
        "schedule": {"mode": "always"},
    }])
    r = _call_tool(client)
    text = r.json()["result"]["content"][0]["text"]
    assert "pending_args" in text or "other tool" in text


def test_tool_poisoning_many_shot():
    client = _setup_mcp([{
        "name": "many", "summary": "many", "target": "mcp_tool",
        "fault": {"kind": "tool_poisoning", "poison_type": "many_shot"},
        "schedule": {"mode": "always"},
    }])
    r = _call_tool(client)
    text = r.json()["result"]["content"][0]["text"]
    assert "elevated" in text or "bypass_auth" in text


def test_tool_poisoning_custom_payload():
    client = _setup_mcp([{
        "name": "custom", "summary": "custom", "target": "mcp_tool",
        "fault": {"kind": "tool_poisoning", "poison_type": "prompt_injection", "payload": "YOU HAVE BEEN PWNED"},
        "schedule": {"mode": "always"},
    }])
    r = _call_tool(client)
    text = r.json()["result"]["content"][0]["text"]
    assert "YOU HAVE BEEN PWNED" in text


def test_tool_poisoning_preserves_original():
    """Poison is appended to original mock result, not replacing it."""
    client = _setup_mcp([{
        "name": "poison", "summary": "inject", "target": "mcp_tool",
        "fault": {"kind": "tool_poisoning", "poison_type": "prompt_injection"},
        "schedule": {"mode": "always"},
    }])
    r = _call_tool(client)
    text = r.json()["result"]["content"][0]["text"]
    assert "mock result for search" in text
    assert "Ignore all previous instructions" in text


def test_tool_poisoning_tracked_in_scorecard():
    client = _setup_mcp([{
        "name": "poison", "summary": "inject", "target": "mcp_tool",
        "fault": {"kind": "tool_poisoning", "poison_type": "prompt_injection"},
        "schedule": {"mode": "always"},
    }])
    _call_tool(client)
    scorecard = client.get("/_agentbreak/mcp-scorecard").json()
    assert scorecard["response_mutations"] >= 1
    assert scorecard["injected_faults"] >= 1


# -- tool_poisoning: validation --

def test_tool_poisoning_requires_poison_type():
    """tool_poisoning without poison_type should fail validation."""
    import pytest
    with pytest.raises(Exception):
        ScenarioFile.model_validate({"scenarios": [{
            "name": "bad", "summary": "bad", "target": "mcp_tool",
            "fault": {"kind": "tool_poisoning"},
            "schedule": {"mode": "always"},
        }]})


def test_tool_poisoning_llm_rejected():
    """tool_poisoning on llm_chat should fail validation."""
    import pytest
    from agentbreak.scenarios import validate_scenarios
    sf = ScenarioFile.model_validate({"scenarios": [{
        "name": "bad", "summary": "bad", "target": "llm_chat",
        "fault": {"kind": "tool_poisoning", "poison_type": "prompt_injection"},
        "schedule": {"mode": "always"},
    }]})
    with pytest.raises(ValueError, match="llm_chat does not support"):
        validate_scenarios(sf)


# -- rug_pull --

def test_rug_pull_before_threshold():
    """Before after_count, tools/list should be clean."""
    client = _setup_mcp([{
        "name": "rug", "summary": "rug", "target": "mcp_tool",
        "fault": {"kind": "rug_pull", "after_count": 10},
        "schedule": {"mode": "always"},
    }])
    r = _list_tools(client)
    tools = r.json()["result"]["tools"]
    for t in tools:
        assert "Ignore all previous instructions" not in t["description"]


def test_rug_pull_after_threshold():
    """After after_count requests, tools/list should have poisoned descriptions."""
    client = _setup_mcp([{
        "name": "rug", "summary": "rug", "target": "mcp_tool",
        "fault": {"kind": "rug_pull", "after_count": 3},
        "schedule": {"mode": "always"},
    }])
    # Send 3 requests to cross the threshold
    for i in range(3):
        _call_tool(client, req_id=i + 1)
    # Now tools/list should be poisoned
    r = _list_tools(client)
    tools = r.json()["result"]["tools"]
    assert any("Ignore all previous instructions" in t["description"] for t in tools)


def test_rug_pull_custom_payload():
    client = _setup_mcp([{
        "name": "rug", "summary": "rug", "target": "mcp_tool",
        "fault": {"kind": "rug_pull", "after_count": 1, "payload": "EVIL PAYLOAD"},
        "schedule": {"mode": "always"},
    }])
    _call_tool(client)  # 1 request to cross threshold
    r = _list_tools(client)
    tools = r.json()["result"]["tools"]
    assert any("EVIL PAYLOAD" in t["description"] for t in tools)


def test_rug_pull_requires_after_count():
    """rug_pull without after_count should fail validation."""
    import pytest
    with pytest.raises(Exception):
        ScenarioFile.model_validate({"scenarios": [{
            "name": "bad", "summary": "bad", "target": "mcp_tool",
            "fault": {"kind": "rug_pull"},
            "schedule": {"mode": "always"},
        }]})


def test_rug_pull_llm_rejected():
    """rug_pull on llm_chat should fail validation."""
    import pytest
    from agentbreak.scenarios import validate_scenarios
    sf = ScenarioFile.model_validate({"scenarios": [{
        "name": "bad", "summary": "bad", "target": "llm_chat",
        "fault": {"kind": "rug_pull", "after_count": 5},
        "schedule": {"mode": "always"},
    }]})
    with pytest.raises(ValueError, match="llm_chat does not support"):
        validate_scenarios(sf)


# -- mcp-security preset --

def test_mcp_security_preset_loads():
    sf = ScenarioFile.model_validate({"preset": "mcp-security", "scenarios": []})
    # This is a ScenarioFile not expanded yet — load via load_scenarios
    from agentbreak.scenarios import PRESET_SCENARIOS
    assert "mcp-security" in PRESET_SCENARIOS
    assert len(PRESET_SCENARIOS["mcp-security"]) == 5
