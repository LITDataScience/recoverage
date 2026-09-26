import http.client
from pathlib import Path

from recoverage.display import serve_html


def test_show_serves_svg_charts_and_rejects_other_paths(tmp_path: Path):
    html = tmp_path / "report.html"
    html.write_text("<!DOCTYPE html><p>report</p>", encoding="utf-8")
    charts = tmp_path / "charts"
    charts.mkdir()
    (charts / "score_gauge.svg").write_text("<svg></svg>", encoding="utf-8")
    (charts / "notes.txt").write_text("nope", encoding="utf-8")
    server = serve_html(html, port=0, open_browser=False, background=True)
    try:
        host, port = server.server_address[:2]
        connection = http.client.HTTPConnection(host, port, timeout=2)
        connection.request("GET", "/charts/score_gauge.svg")
        response = connection.getresponse()
        body = response.read()
        assert response.status == 200
        assert response.getheader("Content-Type") == "image/svg+xml"
        assert body == b"<svg></svg>"
        connection.request("GET", "/charts/notes.txt")
        missing = connection.getresponse()
        missing.read()
        assert missing.status == 404
        connection.request("GET", "/etc/passwd")
        blocked = connection.getresponse()
        blocked.read()
        assert blocked.status == 404
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
