import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREPARE = load_script("prepare_brand_favicon", "prepare-brand-favicon.py")
RENDER = load_script("render_brand_favicon", "render-site.py")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BrandFaviconTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "assets" / "brand" / "01_DS_Favicon_Dark_Mode.png"
        self.derivative = self.root / "assets" / "brand" / "derivatives" / "01_DS_Favicon_Dark_Mode-512.png"
        self.pages = self.root / "docs" / "assets" / "brand" / "01_DS_Favicon_Dark_Mode-512.png"
        self.source.parent.mkdir(parents=True)
        self.write_source((10, 20, 30, 255))
        self.write_manifest("outdated")
        self.old_render_paths = (
            RENDER.BRAND_FAVICON_SOURCE,
            RENDER.BRAND_FAVICON_DERIVATIVE,
            RENDER.OUT,
        )
        RENDER.BRAND_FAVICON_SOURCE = self.source
        RENDER.BRAND_FAVICON_DERIVATIVE = self.derivative
        RENDER.OUT = self.root / "docs"

    def tearDown(self):
        (
            RENDER.BRAND_FAVICON_SOURCE,
            RENDER.BRAND_FAVICON_DERIVATIVE,
            RENDER.OUT,
        ) = self.old_render_paths
        self.temp.cleanup()

    def write_source(self, colour: tuple[int, int, int, int]) -> None:
        with Image.new("RGBA", (1024, 1024), colour) as image:
            image.save(self.source, format="PNG")

    def write_manifest(self, source_checksum: str) -> None:
        manifest = {
            "schema_version": 1,
            "assets": [
                {
                    "path": "01_DS_Favicon_Dark_Mode.png",
                    "sha256": source_checksum,
                    "pages_derivative": {
                        "path": "docs/assets/brand/01_DS_Favicon_Dark_Mode-512.png",
                        "prepared_path": "assets/brand/derivatives/01_DS_Favicon_Dark_Mode-512.png",
                        "source_sha256": source_checksum,
                        "sha256": "outdated",
                        "width": 512,
                        "height": 512,
                        "format": "image/png",
                    },
                }
            ],
        }
        (self.root / "assets" / "brand" / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    def manifest(self) -> dict:
        return json.loads((self.root / "assets" / "brand" / "manifest.json").read_text(encoding="utf-8"))

    def test_preparation_is_byte_stable_and_pages_copy_is_exact(self):
        _, master_checksum, changed = PREPARE.prepare(self.root)
        self.assertTrue(changed)
        self.assertTrue(self.derivative.is_file())
        self.assertEqual(master_checksum, sha256(self.source))
        derivative_checksum = sha256(self.derivative)

        _, _, changed = PREPARE.prepare(self.root)
        self.assertFalse(changed)
        self.assertEqual(sha256(self.derivative), derivative_checksum)

        RENDER.copy_brand_favicon()
        self.assertEqual(self.pages.read_bytes(), self.derivative.read_bytes())

        asset = self.manifest()["assets"][0]
        self.assertEqual(asset["sha256"], master_checksum)
        self.assertEqual(asset["pages_derivative"]["source_sha256"], master_checksum)
        self.assertEqual(asset["pages_derivative"]["sha256"], derivative_checksum)

    def test_master_change_prepares_once_and_tampering_fails_closed(self):
        PREPARE.prepare(self.root)
        first_derivative = sha256(self.derivative)

        self.write_source((90, 80, 70, 255))
        _, new_master_checksum, changed = PREPARE.prepare(self.root)
        self.assertTrue(changed)
        self.assertEqual(new_master_checksum, self.manifest()["assets"][0]["pages_derivative"]["source_sha256"])
        self.assertNotEqual(sha256(self.derivative), first_derivative)

        _, _, changed = PREPARE.prepare(self.root)
        self.assertFalse(changed)

        self.derivative.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "checksum is inconsistent"):
            PREPARE.prepare(self.root)


if __name__ == "__main__":
    unittest.main()
