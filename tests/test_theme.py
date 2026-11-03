"""The UI must not load anything from the internet (privacy promise in docs/USER_GUIDE.md)."""

import re
from pathlib import Path

from pdfragen import theme

REPO = Path(__file__).resolve().parent.parent


def test_page_css_has_no_external_urls():
    assert not re.search(r"https?://", theme.page_css())


def test_every_font_url_points_to_a_bundled_file():
    urls = re.findall(r"url\('/app/static/([^']+)'\)", theme.page_css())
    assert urls, "expected self-hosted @font-face rules"
    for rel in urls:
        assert (REPO / "static" / rel).is_file(), rel
