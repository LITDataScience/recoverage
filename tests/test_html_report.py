import hashlib
import base64
import re

from recoverage.html_report import build_html
from recoverage.models import Gap
from tests.test_html import _analysis


def _hashes(page: str) -> tuple[str, str]:
    style = re.search(r"<style>(.*)</style>", page, re.S).group(1)
    script = re.search(r"<script>(.*)</script>", page, re.S).group(1)

    def digest(text: str) -> str:
        return "sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()

    return digest(style), digest(script)


def test_dashboard_csp_matches_and_escapes_hostile_text():
    analysis = _analysis()
    analysis.gaps.append(
        Gap("G02", "high", "xss", "<script>alert(1)</script>", "why", "a.py", "boom", "see https://evil.example", False)
    )
    page = build_html(analysis, {})
    style_hash, script_hash = _hashes(page)
    assert style_hash in page
    assert script_hash in page
    assert 'src="http' not in page
    assert "href=\"http" not in page
    assert "<script>alert" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "G01" in page and "G02" in page
    assert "<script src=" not in page
    assert 'rel="stylesheet"' not in page


def test_dashboard_with_no_gaps_still_renders():
    analysis = _analysis()
    analysis.gaps.clear()
    page = build_html(analysis, {})
    assert "No gaps recorded." in page
    assert "Suggestions" in page
    assert "32.5" in page
