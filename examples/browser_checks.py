"""Drive the real Streamlit app in Chrome for the browser checks in SECURITY_ASSESSMENT.md.

Checks (each repeated ``--runs`` times):
  xss        HTML payload in PDF text rendered in "Read the cited passages" (A3)
  fname      HTML payload in the upload filename (A3b)
  replace    same session: secret doc replaced by another, ask for the secret (A4a)
  parallel   two sessions: B asks for A's secret (A4b)
  traversal  upload named "../../<probe>.pdf" lands outside the session dir (A5)

Playwright is not a project dependency; install it in a separate venv. It uses
the installed Google Chrome, so no browser download is needed:

    python examples/make_attack_samples.py
    streamlit run app.py --server.headless true --server.port 8599 --server.address 127.0.0.1
    python -m venv /tmp/pw && /tmp/pw/bin/pip install playwright
    /tmp/pw/bin/python examples/browser_checks.py --url http://127.0.0.1:8599 --out browser.json

The app needs Ollama with the configured model (the checks ask real questions).
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from make_attack_samples import OUT_DIR as ATTACKS, SECRET
from playwright.sync_api import sync_playwright

LECTURE = Path(__file__).parent / "vorlesung_maschinelles_lernen.pdf"
SECRET_PDF = ATTACKS / "a4_second_document.pdf"
QUESTION = "What is the deadline for applying for the extension?"
SECRET_QUESTION = "What is my customer number (Kundennummer) and my monthly rent?"
# The app saves uploads in tempfile.mkdtemp() dirs, so "../" from there is the
# parent of the temp dir. Assumes the app runs as the same user on this machine.
TRAVERSAL_NAME = "../pdfragen_traversal_probe.pdf"
TRAVERSAL_TARGET = Path(tempfile.gettempdir()) / "pdfragen_traversal_probe.pdf"
ANSWER_TIMEOUT_MS = 300_000


def new_page(browser, url):
    page = browser.new_context().new_page()
    page.goto(url)
    page.locator('input[type="file"]').first.wait_for(state="attached", timeout=60_000)
    return page


def upload(page, path=None, name=None, data=None):
    files = str(path) if path else {"name": name, "mimeType": "application/pdf", "buffer": data}
    page.locator('input[type="file"]').first.set_input_files(files)
    page.locator('[data-testid="stChatInputTextArea"]:not([disabled])').wait_for(
        timeout=120_000
    )
    page.wait_for_timeout(1500)


def ask(page, question):
    """Ask ``question`` and return the assistant message, with passages expanded."""
    before = page.locator('[data-testid="stChatMessage"]').count()
    box = page.locator('[data-testid="stChatInputTextArea"]')
    box.fill(question)
    box.press("Enter")
    msg = page.locator('[data-testid="stChatMessage"]').nth(before + 1)
    expander = msg.get_by_text("Read the cited passages")
    expander.or_(msg.locator(".pf-notice")).first.wait_for(timeout=ANSWER_TIMEOUT_MS)
    page.wait_for_timeout(1500)
    if expander.count():
        expander.click()
        page.wait_for_timeout(800)
    return msg


def check_xss(browser, url):
    page = new_page(browser, url)
    upload(page, ATTACKS / "a3_xss.pdf")
    ask(page, QUESTION)
    img = page.locator(".pf-passage img")
    result = {
        "js_fired": page.title() == "XSS-FIRED",
        "img_in_dom": img.count(),
        "img_html": img.first.evaluate("e => e.outerHTML") if img.count() else None,
        "fake_box_in_dom": page.locator('.pf-passage div[style*="background"]').count(),
        "evil_link_in_dom": page.locator('.pf-passage a[href*="evil.example"]').count(),
    }
    page.context.close()
    return result


def check_filename(browser, url):
    page = new_page(browser, url)
    name = "<img src=y onerror=\"document.title='FILENAME-XSS'\">.pdf"
    upload(page, name=name, data=SECRET_PDF.read_bytes())
    result = {
        "js_fired": page.title() == "FILENAME-XSS",
        "img_in_dom": page.locator('img[src="y"]').count(),
    }
    page.context.close()
    return result


def check_replace(browser, url):
    page = new_page(browser, url)
    upload(page, SECRET_PDF)
    upload(page, LECTURE)
    msg = ask(page, SECRET_QUESTION)
    result = {"leaked": SECRET in msg.inner_text(), "message": msg.inner_text()[:500]}
    page.context.close()
    return result


def check_parallel(browser, url):
    owner, other = new_page(browser, url), new_page(browser, url)
    upload(owner, SECRET_PDF)
    upload(other, LECTURE)
    msg = ask(other, SECRET_QUESTION)
    result = {"leaked": SECRET in msg.inner_text(), "message": msg.inner_text()[:500]}
    owner.context.close()
    other.context.close()
    return result


def check_traversal(browser, url):
    TRAVERSAL_TARGET.unlink(missing_ok=True)
    page = new_page(browser, url)
    page.locator('input[type="file"]').first.set_input_files(
        {"name": TRAVERSAL_NAME, "mimeType": "application/pdf", "buffer": SECRET_PDF.read_bytes()}
    )
    page.wait_for_timeout(8000)  # let the app save and index the upload
    escaped = TRAVERSAL_TARGET.exists()
    TRAVERSAL_TARGET.unlink(missing_ok=True)
    page.context.close()
    return {"written_outside_session_dir": escaped}


CHECKS = {
    "xss": (check_xss, "js_fired"),
    "fname": (check_filename, "js_fired"),
    "replace": (check_replace, "leaked"),
    "parallel": (check_parallel, "leaked"),
    "traversal": (check_traversal, "written_outside_session_dir"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8599")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--checks", default=",".join(CHECKS), help="comma-separated")
    args = parser.parse_args()

    report = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for name in args.checks.split(","):
            check, key = CHECKS[name]
            runs = [check(browser, args.url) for _ in range(args.runs)]
            report[name] = runs
            print(f"{name}: {key} in {sum(bool(r[key]) for r in runs)}/{len(runs)}")
            if name in ("xss", "fname"):
                print(f"  html elements in DOM: {[r['img_in_dom'] for r in runs]}")
        browser.close()

    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nfull results: {args.out}")


if __name__ == "__main__":
    main()
