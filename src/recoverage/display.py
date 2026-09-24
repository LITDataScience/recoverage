"""Open the HTML file that run/report already wrote. This does not build a second report."""

from __future__ import annotations

import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def locate_html(path: Path, output: Path | None = None) -> Path:
    if path.is_file() and path.suffix.lower() == ".html":
        return path.resolve()
    candidates = []
    if output is not None:
        candidates.append(output / "report.html")
    candidates.append(path / "report.html")
    candidates.append(path / "recoverage-out" / "report.html")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    looked = ", ".join(str(item) for item in candidates)
    raise FileNotFoundError(f"no report.html at {looked}. Run `recoverage run` or `recoverage report` first.")


def serve_html(html_path: Path, *, port: int = 0, open_browser: bool = True, background: bool = False) -> ThreadingHTTPServer:
    """Serve the existing file. `background=True` returns the server instead of blocking."""
    target = html_path.resolve()
    payload = target.read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            route = self.path.split("?", 1)[0]
            if route not in {"/", "/report.html"}:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt: str, *args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    host, bound = server.server_address[:2]
    url = f"http://{host}:{bound}/report.html"
    print(f"Serving {target} at {url}")
    if open_browser:
        webbrowser.open(url)
    if background:
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return server
