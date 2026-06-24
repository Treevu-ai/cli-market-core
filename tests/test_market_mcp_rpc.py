"""JSON-RPC handshake tests for market-mcp stdio server."""

from market_core.market_mcp import handle_rpc_request


def test_notifications_initialized_returns_no_response():
    request = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    assert handle_rpc_request(request, "default") is None


def test_initialize_returns_valid_result():
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }
    response = handle_rpc_request(request, "default")
    assert response is not None
    assert response["id"] == 1
    assert "result" in response
    assert response["result"]["protocolVersion"] == "2024-11-05"
    assert response["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert response["result"]["serverInfo"]["name"] == "cli-market"
    assert "error" not in response


def test_initialize_negotiates_2025_03_26_for_cursor():
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {"roots": {"listChanged": True}},
            "clientInfo": {"name": "cursor", "version": "1.0.0"},
        },
    }
    response = handle_rpc_request(request, "default")
    assert response is not None
    assert response["result"]["protocolVersion"] == "2025-03-26"


def test_unknown_method_with_id_returns_jsonrpc_error():
    request = {"jsonrpc": "2.0", "id": 99, "method": "nope/missing"}
    response = handle_rpc_request(request, "default")
    assert response == {
        "jsonrpc": "2.0",
        "id": 99,
        "error": {"code": -32601, "message": "Method not found: nope/missing"},
    }


def test_ping_returns_empty_result():
    request = {"jsonrpc": "2.0", "id": "ping-1", "method": "ping"}
    response = handle_rpc_request(request, "default")
    assert response == {"jsonrpc": "2.0", "id": "ping-1", "result": {}}
