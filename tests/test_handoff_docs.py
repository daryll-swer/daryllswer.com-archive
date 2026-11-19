from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
README_TITLE = "# daryllswer.com \u2013 Archive"
ARCHIVE_LINK = (
    "**Read the archive:** [daryllswer.com \u2013 Archive]"
    "(https://daryll-swer.github.io/daryllswer.com-archive/)"
)
AI_FOOTER = (
    "Start with [AGENTS.md](AGENTS.md), then read [PLANS.md](PLANS.md) and "
    "[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md). Verify the current "
    "repository state before acting; historical records are not current authorisation."
)
CURRENT_DOCS = ("README.md", "AGENTS.md", "PLANS.md", "IMPLEMENTATION_STATUS.md", "docs/HANDOFF.md")
HISTORY_DOCS = (
    "docs/history/PLANS-through-2026-11-16.md",
    "docs/history/IMPLEMENTATION_STATUS-through-2026-11-16.md",
)
ASSET_LINKS = {
    "README header logo": "assets/readme/13_DS_Logo_Dark_Mode_SEO.png",
    "GitHub Pages favicon source": "assets/brand/01_DS_Favicon_Dark_Mode.png",
    "generated derivative": "assets/brand/derivatives/01_DS_Favicon_Dark_Mode-512.png",
    "byte-for-byte GitHub Pages favicon": "docs/assets/brand/01_DS_Favicon_Dark_Mode-512.png",
}
CONTROLLING_NOTICES = {
    "LICENSES/DARYLL-SWER-PROPRIETARY-CONTENT-NOTICE.txt",
    "LICENSES/SWER-NETWORKS-PROPRIETARY-CONTENT-NOTICE.txt",
    "LICENSES/DARYLL-SWER-PROPRIETARY-ASSET-NOTICE.txt",
}
INLINE_LINK = re.compile(r"\[([^\]\n]+)\]\(\s*(?:<([^>\n]+)>|([^\s)]+))\s*\)")
FENCED_CODE = re.compile(r"^\x60{3,}[^\n]*\n.*?^\x60{3,}[ \t]*$", re.MULTILINE | re.DOTALL)
WORKER_CONFIG = re.compile(
    r"\b(?:gpt-\d+(?:\.\d+)?-(?:astra|luna|sol)|(?:implementer|explorer)-(?:luna|sol)"
    r"|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\b",
    re.IGNORECASE,
)


def markdown_links(text: str) -> set[tuple[str, str]]:
    return {(label, angled or bare) for label, angled, bare in INLINE_LINK.findall(FENCED_CODE.sub("", text))}


def heading_anchors(text: str) -> set[str]:
    headings = re.findall(r"^#{1,6}\s+(.+)$", FENCED_CODE.sub("", text), re.MULTILINE)
    return {re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-") for heading in headings}


class HandoffDocsTests(unittest.TestCase):
    def test_readme_opens_with_archive_link_before_logo_and_ends_with_ai_footer(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(text.split("\n\n", 2)[:2], [README_TITLE, ARCHIVE_LINK])
        self.assertIn(f'<img src="{ASSET_LINKS["README header logo"]}"', text)
        _, heading, footer = text.rpartition("\n## For AI Agents\n")
        self.assertTrue(heading)
        self.assertEqual(" ".join(footer.split()), AI_FOOTER)

    def test_readme_retains_semantic_asset_links_and_controlling_notices(self) -> None:
        links = markdown_links((ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertLessEqual(ASSET_LINKS.items(), links)
        self.assertLessEqual(CONTROLLING_NOTICES, {target for _, target in links})

    def test_agents_links_to_fresh_handoff_inputs(self) -> None:
        links = markdown_links((ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertLessEqual(
            {"PLANS.md", "IMPLEMENTATION_STATUS.md", "docs/HANDOFF.md"},
            {target for _, target in links},
        )

    def test_handoff_relative_links_and_fragments_resolve(self) -> None:
        for relative in (*CURRENT_DOCS, *HISTORY_DOCS):
            doc = ROOT / relative
            text = doc.read_text(encoding="utf-8")
            if relative in HISTORY_DOCS:
                text = text.partition("\n## ")[0]
                self.assertLessEqual(
                    {"../../PLANS.md", "../../IMPLEMENTATION_STATUS.md"},
                    {target for _, target in markdown_links(text)},
                )
            for _, target in sorted(markdown_links(text)):
                url = urlsplit(target)
                if url.scheme or url.netloc:
                    continue
                with self.subTest(document=relative, link=target):
                    destination = (doc.parent / unquote(url.path)).resolve() if url.path else doc
                    self.assertTrue(destination.is_relative_to(ROOT))
                    self.assertTrue(destination.exists())
                    if url.fragment and destination.suffix == ".md":
                        self.assertIn(unquote(url.fragment), heading_anchors(destination.read_text(encoding="utf-8")))

    def test_current_root_docs_do_not_embed_worker_runtime_configuration(self) -> None:
        for relative in ("PLANS.md", "IMPLEMENTATION_STATUS.md"):
            with self.subTest(document=relative):
                self.assertNotRegex((ROOT / relative).read_text(encoding="utf-8"), WORKER_CONFIG)


if __name__ == "__main__":
    unittest.main()
