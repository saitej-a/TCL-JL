"""Placeholder web responder for Phase 1.1 (D-01).

Binds 0.0.0.0:8000 — the container-local loopback is unreachable through
the bridge network. Phase 1.2 swaps this entrypoint for gunicorn.
"""

import http.server
import socketserver

PORT = 8000
BODY = b"TCS Joining Tracker - placeholder web (Phase 1.1)\n"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        self.wfile.write(BODY)

    def log_message(self, *args):
        pass


def main():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as srv:
        print(f"[web placeholder] serving on 0.0.0.0:{PORT}", flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
