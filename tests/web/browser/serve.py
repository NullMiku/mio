"""Static server for the built playground that records every request (method, path, body size)."""
import http.server
import json
import sys
from pathlib import Path

port, root = int(sys.argv[1]), Path(sys.argv[2]).resolve()
log = Path(__file__).resolve().parents[3] / "build/web-report/requests.jsonl"
log.parent.mkdir(parents=True, exist_ok=True)
log.write_text("")


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm", ".js": "text/javascript"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(root), **kwargs)

    def record(self):
        length = int(self.headers.get("Content-Length") or 0)
        with log.open("a") as out:
            out.write(json.dumps(dict(method=self.command, path=self.path, body=length)) + "\n")

    def do_GET(self):
        self.record()
        super().do_GET()

    def do_POST(self):
        self.record()
        self.send_error(405)

    do_PUT = do_POST

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
