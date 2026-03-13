import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.privacy import is_session_listing_enabled


class SessionPrivacyTests(unittest.TestCase):
    def test_defaults_to_public_session_listing(self):
        self.assertTrue(is_session_listing_enabled({}))

    def test_private_first_disables_listing(self):
        branding = {"privacy": {"privateFirst": True}}
        self.assertFalse(is_session_listing_enabled(branding))

    def test_explicit_allow_session_listing_overrides_private_first(self):
        branding = {"privacy": {"privateFirst": True, "allowSessionListing": True}}
        self.assertTrue(is_session_listing_enabled(branding))

    def test_explicit_disable_session_listing(self):
        branding = {"privacy": {"allowSessionListing": False}}
        self.assertFalse(is_session_listing_enabled(branding))


if __name__ == "__main__":
    unittest.main()
