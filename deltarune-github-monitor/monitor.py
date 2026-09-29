from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from playwright.sync_api import sync_playwright

URLS = [
    "https://deltarune.com/chapter5/",
    "https://deltarune.com/7b/",
]

STATE_DIR = Path("state")
WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]


def key(url: str) -> str:
    path = urlparse(url).path.strip("/").replace("/", "_")
    return path or "homepage"


def norm_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            out.append(line)
    return "\n".join(out)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def render(page, url: str) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3000)

    # Remove highly dynamic nodes from the comparison.
    visible = norm_text(page.locator("body").inner_text(timeout=10000))

    dom = page.evaluate("""
        () => {
          const clone = document.body.cloneNode(true);
          clone.querySelectorAll('script, style, noscript, template').forEach(e => e.remove());

          const resources = [...document.querySelectorAll(
            'img[src], source[src], video[src], audio[src], link[href], a[href]'
          )].map(e => {
            const attr = e.hasAttribute('src') ? 'src' : 'href';
            return `${e.tagName}|${attr}|${e.getAttribute(attr)}`;
          }).sort();

          return clone.innerHTML + "\\n__RESOURCES__\\n" + resources.join("\\n");
        }
    """)

    page.add_style_tag(content="""
        *, *::before, *::after {
          animation: none !important;
          transition: none !important;
          caret-color: transparent !important;
        }
    """)
    page.wait_for_timeout(500)

    # The screenshot hash catches visual changes that do not alter visible text.
    png = page.screenshot(type="png", full_page=True, animations="disabled")
    screenshot_hash = hashlib.sha256(png).hexdigest()

    return {
        "url": url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "text": visible,
        "text_hash": sha(visible),
        "dom_hash": sha(dom),
        "screenshot_hash": screenshot_hash,
    }


def diff(old: str, new: str) -> str:
    lines = list(difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile="previous",
        tofile="current",
        lineterm=""
    ))
    return "\n".join(lines[:100])


def notify(result: dict, old: dict | None):
    changes = []
    if old is None:
        changes.append("initial baseline")
    else:
        if old.get("text_hash") != result["text_hash"]:
            changes.append("visible text")
        if old.get("dom_hash") != result["dom_hash"]:
            changes.append("DOM/resources")
        if old.get("screenshot_hash") != result["screenshot_hash"]:
            changes.append("visual appearance")

    if not changes:
        return

    description = (
        f"**Changed:** {', '.join(changes)}\n"
        f"**URL:** {result['url']}\n"
        f"**Checked:** {result['checked_at']}\n"
    )

    if old and old.get("text_hash") != result["text_hash"]:
        d = diff(old.get("text", ""), result.get("text", ""))
        if d:
            description += f"\n```diff\n{d[:1400]}\n```"

    payload = {
        "username": "Deltarune Site Monitor",
        "content": "🚨 Deltarune site change detected!",
        "embeds": [{
            "title": key(result["url"]),
            "description": description,
            "url": result["url"],
        }]
    }

    r = requests.post(WEBHOOK, json=payload, timeout=30)
    r.raise_for_status()


def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1600})

        for url in URLS:
            state_file = STATE_DIR / f"{key(url)}.json"

            result = render(page, url)
            old = None

            if state_file.exists():
                old = json.loads(state_file.read_text(encoding="utf-8"))

            # First run establishes the baseline and sends no notification.
            if old is not None:
                notify(result, old)

            state_file.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

        browser.close()


if __name__ == "__main__":
    main()
