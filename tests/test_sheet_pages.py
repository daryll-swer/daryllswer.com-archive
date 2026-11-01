import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from sheet_pages import refresh_sheet_pages


class SheetPagesTests(unittest.TestCase):
    def test_refresh_is_offline_deterministic_and_updates_only_html_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sheet_dir = root / "data" / "sheets" / "fixture"
            csv_path = sheet_dir / "csv" / "prefixes.csv"
            csv_path.parent.mkdir(parents=True)
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Prefix", "Purpose", "Notes"])
                writer.writerow(["2001:db8::/32", "Documentation", "Fixture prefix"])

            manifest = {
                "generated_at": "2026-01-01T00:00:00Z",
                "source_url": "https://docs.google.com/spreadsheets/example",
                "title": "Fixture workbook",
                "ods": {"path": "data/sheets/fixture/example.ods"},
                "published_workbook_html": {"path": "data/sheets/fixture/html/published.html"},
                "tabs": [{
                    "name": "Prefixes",
                    "csv": {"path": "data/sheets/fixture/csv/prefixes.csv"},
                    "html": {"path": "data/sheets/fixture/html/prefixes.html"},
                    "csvw": {"path": "data/sheets/fixture/csvw/prefixes.json"},
                }],
                "custom_metadata": {"preserve": True},
            }
            (sheet_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            first = refresh_sheet_pages(root, sheet_dir, dict(manifest))
            visual = (sheet_dir / "visual.html").read_bytes()
            workbook = (sheet_dir / "workbook.html").read_bytes()
            second = refresh_sheet_pages(root, sheet_dir, dict(manifest))

            self.assertEqual(visual, (sheet_dir / "visual.html").read_bytes())
            self.assertEqual(workbook, (sheet_dir / "workbook.html").read_bytes())
            self.assertEqual(first, second)
            self.assertIn(b"Skip to content", visual)
            self.assertIn(b"../../sitemap.xml", visual)
            self.assertIn(b"@media print", visual)
            self.assertIn(b"Skip to content", workbook)
            self.assertIn(b'role="region" tabindex="0" aria-label="Prefixes data"', workbook)
            self.assertEqual(first["visual_model"]["sha256"], hashlib.sha256(visual).hexdigest())
            self.assertEqual(first["visual_model"]["bytes"], len(visual))
            self.assertEqual(first["workbook_html"]["sha256"], hashlib.sha256(workbook).hexdigest())
            self.assertEqual(first["workbook_html"]["bytes"], len(workbook))
            self.assertTrue(first["custom_metadata"]["preserve"])


if __name__ == "__main__":
    unittest.main()
