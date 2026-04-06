"""Tests for MCP tool call validation."""
from fastapi.testclient import TestClient
from agentbreak import main
from agentbreak.config import MCPRegistry, MCPTool, MCPResource, MCPPrompt
from agentbreak.main import validate_tool_call, _field_allows_null


# -- Registry fixtures --

REGISTRY = MCPRegistry(
    tools=[
        MCPTool(name="save_issue", description="Create issue", inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "team": {"type": "string"},
                "priority": {"type": "number"},
                "labels": {"type": "array", "items": {"type": "string"}},
                "assignee": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            },
            "required": ["title", "team"],
        }),
        MCPTool(name="list_issues", description="List issues", inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer"},
            },
        }),
        MCPTool(name="no_schema", description="No schema tool"),
    ],
)


def _setup_mcp():
    main.service_state.mcp_runtime = main.MCPRuntime(
        upstream_url="", auth_headers={},
        registry=REGISTRY,
        scenarios=[],
    )
    return TestClient(main.app)


# -- Unit tests for validate_tool_call --

def test_valid_call():
    err = validate_tool_call("save_issue", {"title": "Bug", "team": "Eng"}, REGISTRY)
    assert err is None


def test_valid_call_with_optional_fields():
    err = validate_tool_call("save_issue", {"title": "Bug", "team": "Eng", "priority": 2, "labels": ["urgent"]}, REGISTRY)
    assert err is None


def test_unknown_tool():
    err = validate_tool_call("nonexistent", {"foo": "bar"}, REGISTRY)
    assert err is not None
    assert err["error"] == "unknown_tool"


def test_missing_required():
    err = validate_tool_call("save_issue", {"title": "Bug"}, REGISTRY)
    assert err is not None
    assert err["error"] == "missing_required"
    assert "team" in err["missing"]


def test_wrong_type_string_got_int():
    err = validate_tool_call("save_issue", {"title": 12345, "team": "Eng"}, REGISTRY)
    assert err is not None
    assert err["error"] == "type_mismatch"
    assert err["fields"][0]["field"] == "title"
    assert err["fields"][0]["got"] == "int"


def test_wrong_type_number_got_string():
    err = validate_tool_call("save_issue", {"title": "Bug", "team": "Eng", "priority": "high"}, REGISTRY)
    assert err is not None
    assert err["error"] == "type_mismatch"
    assert err["fields"][0]["field"] == "priority"


def test_wrong_type_array_got_string():
    err = validate_tool_call("save_issue", {"title": "Bug", "team": "Eng", "labels": "urgent"}, REGISTRY)
    assert err is not None
    assert err["error"] == "type_mismatch"
    assert err["fields"][0]["field"] == "labels"


def test_null_on_non_nullable_field():
    """null on a field that doesn't allow null should be caught."""
    err = validate_tool_call("save_issue", {"title": None, "team": "Eng"}, REGISTRY)
    assert err is not None
    assert err["error"] == "type_mismatch"
    assert err["fields"][0]["field"] == "title"
    assert err["fields"][0]["got"] == "null"


def test_null_on_nullable_field():
    """null on an anyOf [..., null] field should be valid."""
    err = validate_tool_call("save_issue", {"title": "Bug", "team": "Eng", "assignee": None}, REGISTRY)
    assert err is None


def test_anyof_field_correct_type():
    """String value on an anyOf [string, null] field should be valid."""
    err = validate_tool_call("save_issue", {"title": "Bug", "team": "Eng", "assignee": "alice"}, REGISTRY)
    assert err is None


def test_anyof_field_wrong_type():
    """Number on an anyOf [string, null] field should be caught."""
    err = validate_tool_call("save_issue", {"title": "Bug", "team": "Eng", "assignee": 123}, REGISTRY)
    assert err is not None
    assert err["error"] == "type_mismatch"
    assert err["fields"][0]["field"] == "assignee"


def test_arguments_null():
    """arguments: null should return invalid_arguments, not crash."""
    err = validate_tool_call("save_issue", None, REGISTRY)
    assert err is not None
    assert err["error"] == "invalid_arguments"


def test_arguments_list():
    """arguments: [] should return invalid_arguments."""
    err = validate_tool_call("save_issue", [], REGISTRY)
    assert err is not None
    assert err["error"] == "invalid_arguments"


def test_arguments_string():
    """arguments: 'foo' should return invalid_arguments."""
    err = validate_tool_call("save_issue", "foo", REGISTRY)
    assert err is not None
    assert err["error"] == "invalid_arguments"


def test_no_schema_tool():
    """Tool with no inputSchema should always pass validation."""
    err = validate_tool_call("no_schema", {"anything": "goes"}, REGISTRY)
    assert err is None


def test_extra_fields_ok():
    """Extra fields not in schema should not cause errors."""
    err = validate_tool_call("save_issue", {"title": "Bug", "team": "Eng", "extra_field": "value"}, REGISTRY)
    assert err is None


def test_empty_arguments():
    """Empty dict should fail if required fields exist."""
    err = validate_tool_call("save_issue", {}, REGISTRY)
    assert err is not None
    assert err["error"] == "missing_required"


def test_empty_string_values():
    """Empty strings are still strings — should pass type check."""
    err = validate_tool_call("save_issue", {"title": "", "team": ""}, REGISTRY)
    assert err is None


# -- Unit tests for _field_allows_null --

def test_field_allows_null_anyof():
    assert _field_allows_null({"anyOf": [{"type": "string"}, {"type": "null"}]}) is True


def test_field_allows_null_type_array():
    assert _field_allows_null({"type": ["string", "null"]}) is True


def test_field_allows_null_explicit():
    assert _field_allows_null({"type": "null"}) is True


def test_field_disallows_null():
    assert _field_allows_null({"type": "string"}) is False


def test_field_disallows_null_anyof_no_null():
    assert _field_allows_null({"anyOf": [{"type": "string"}, {"type": "integer"}]}) is False


# -- Integration tests through the proxy --

def test_proxy_validation_valid_call():
    client = _setup_mcp()
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "save_issue", "arguments": {"title": "Bug", "team": "Eng"}}})
    assert r.status_code == 200
    scorecard = client.get("/_agentbreak/mcp-scorecard").json()
    assert scorecard["tool_validation"]["valid"] >= 1


def test_proxy_validation_unknown_tool():
    client = _setup_mcp()
    client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "fake_tool", "arguments": {}}})
    scorecard = client.get("/_agentbreak/mcp-scorecard").json()
    assert scorecard["tool_validation"]["unknown_tool"] >= 1


def test_proxy_validation_schema_violation():
    client = _setup_mcp()
    client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "save_issue", "arguments": {"title": 999, "team": "Eng"}}})
    scorecard = client.get("/_agentbreak/mcp-scorecard").json()
    assert scorecard["tool_validation"]["schema_violations"] >= 1


def test_proxy_validation_null_arguments():
    """arguments: null should not crash the proxy."""
    client = _setup_mcp()
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "save_issue", "arguments": None}})
    assert r.status_code == 200  # should not be 500
    scorecard = client.get("/_agentbreak/mcp-scorecard").json()
    assert scorecard["tool_validation"]["schema_violations"] >= 1


def test_proxy_validation_list_arguments():
    """arguments: [] should not crash the proxy."""
    client = _setup_mcp()
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "save_issue", "arguments": []}})
    assert r.status_code == 200
    scorecard = client.get("/_agentbreak/mcp-scorecard").json()
    assert scorecard["tool_validation"]["schema_violations"] >= 1


def test_proxy_null_params():
    """params: null should not crash the proxy."""
    client = _setup_mcp()
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": None})
    assert r.status_code == 200


def test_proxy_tool_coverage():
    client = _setup_mcp()
    client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "save_issue", "arguments": {"title": "Bug", "team": "Eng"}}})
    scorecard = client.get("/_agentbreak/mcp-scorecard").json()
    cov = scorecard["tool_coverage"]
    assert "save_issue" in cov["called"]
    assert "list_issues" in cov["not_called"]
    assert len(cov["registered"]) == 3
