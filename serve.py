#!/usr/bin/env python3
"""Serve FieldGo statically and inject optional Copernicus config from env.

  COPERNICUS_ACCESS_TOKEN=... python3 serve.py

Token is never written to disk. Plain http.server also works; then config.js
is missing and the UI uses public Sentinel tiles only.
"""
from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8000"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path.split("?", 1)[0] in ("/config.js", "/config.js/"):
            token = os.environ.get("COPERNICUS_ACCESS_TOKEN", "").strip()
            body = (
                "window.FIELDGO_CONFIG = "
                + json.dumps({"copernicusToken": token})
                + ";\n"
            )
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        return super().do_GET()


def main() -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    has = bool(os.environ.get("COPERNICUS_ACCESS_TOKEN", "").strip())
    print(f"FieldGo at http://127.0.0.1:{PORT}/")
    print(
        "COPERNICUS_ACCESS_TOKEN: "
        + ("set (injected into /config.js, not saved)" if has else "not set — public Sentinel tiles only")
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
