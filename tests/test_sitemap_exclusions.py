import importlib.util
import sys
import unittest
from pathlib import Path


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


VALIDATOR = load_script("validate_mirror_sitemap", "validate-mirror.py")
NOINDEX_MIRROR = "https://www.daryllswer.com/bgp-router-id-structuring-in-ipv6-native-networks/"
ORDINARY_POST = "https://www.daryllswer.com/example-post/"


class SitemapExclusionTests(unittest.TestCase):
    def test_only_documented_noindex_mirror_is_excluded_from_warning(self):
        missing, unexpected, intentional = VALIDATOR.classify_sitemap_difference(
            {ORDINARY_POST}, {ORDINARY_POST, NOINDEX_MIRROR}
        )

        self.assertEqual(missing, [])
        self.assertEqual(unexpected, [])
        self.assertEqual(
            intentional,
            [(NOINDEX_MIRROR, VALIDATOR.INTENTIONAL_SITEMAP_EXCLUSIONS[NOINDEX_MIRROR])],
        )

    def test_an_unknown_sitemap_absence_remains_a_warning_candidate(self):
        missing, unexpected, intentional = VALIDATOR.classify_sitemap_difference(
            set(), {NOINDEX_MIRROR, ORDINARY_POST}
        )

        self.assertEqual(missing, [])
        self.assertEqual(unexpected, [ORDINARY_POST])
        self.assertEqual(
            intentional,
            [(NOINDEX_MIRROR, VALIDATOR.INTENTIONAL_SITEMAP_EXCLUSIONS[NOINDEX_MIRROR])],
        )


if __name__ == "__main__":
    unittest.main()
