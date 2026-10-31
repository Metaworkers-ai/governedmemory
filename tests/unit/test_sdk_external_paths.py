"""Exercise URL encoding through the SDK's real urllib HTTP transport."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote, urlsplit

import pytest
from metaworkers import GovernedMemory


@pytest.fixture
def external_memory_server():
    class Handler(BaseHTTPRequestHandler):
        def handle_request(self):
            parts = urlsplit(self.path)
            prefix = "/v1/external-memories/"
            path = parts.path.removeprefix(prefix)
            memory_id, _, operation = path.rpartition("/")
            result = {"external_memory_id": unquote(memory_id), "operation": operation}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        do_GET = handle_request
        do_POST = handle_request

        def log_message(self, *_args):
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join(timeout=5)


@pytest.mark.parametrize(
    "memory_id", ["plain-id", "id?revision=2", "id#section", "id%2Fpart", "has space", "mémoire"]
)
@pytest.mark.parametrize("operation", ["governance", "quarantine"])
def test_external_memory_ids_survive_http_transport(external_memory_server, memory_id, operation):
    client = GovernedMemory(external_memory_server, "test-key")
    if operation == "governance":
        result = client.get_external_governance(memory_id)
    else:
        result = client.quarantine_external_memory(memory_id)
    assert result == {"external_memory_id": memory_id, "operation": operation}
