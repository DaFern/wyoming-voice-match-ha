"""Distribution links do not adopt keys, install Core code or hide legacy setup."""

from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUIDE = "https://github.com/DaFern/ha-codex-multi-assist/blob/main/docs/INSTALLATION.md"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attributes):
        if tag == "a":
            self.links.append(dict(attributes))


class DistributionDocsTests(unittest.TestCase):
    def test_readme_baseline_matches_manifest_and_current_changelog(self):
        config = (ROOT / "voice_match/config.yaml").read_text()
        version = re.search(r'^version: "([^"]+)"$', config, re.MULTILINE).group(1)
        readme = (ROOT / "README.md").read_text()
        self.assertIn(f"Add-on baseline **{version}**", readme)
        self.assertIn(f"## {version}\n", (ROOT / "voice_match/CHANGELOG.md").read_text())
        self.assertIn(f'io.hass.version="{version}"', (ROOT / "voice_match/Dockerfile").read_text())
        self.assertNotIn("current 0.4.2 source", readme)

    def test_management_setup_link_is_static_external_guide_not_credential_adoption(self):
        html = (ROOT / "voice_match/rootfs/opt/voice_match/static/index.html").read_text()
        page = Links()
        page.feed(html)
        guides = [link for link in page.links if link.get("href") == GUIDE]
        self.assertEqual(len(guides), 1)
        self.assertEqual(guides[0]["target"], "_blank")
        self.assertEqual(set(guides[0]["rel"].split()), {"noopener", "noreferrer"})
        self.assertEqual(guides[0]["referrerpolicy"], "no-referrer")
        self.assertIn("development only, not a published beta", html)
        self.assertIn("This link installs nothing, shares no key", html)
        self.assertIn('id="open-learning-app"', html)
        self.assertIn("Voice Match Enrolment (Prototype)", html)
        self.assertIn("Codex Assist → Voice Match learning", html)

    def test_standalone_path_stays_documented_until_replacement_acceptance(self):
        standalone = (ROOT / "docs/ENROLLMENT_COMPANION.md").read_text()
        self.assertIn(GUIDE, standalone)
        self.assertIn("Voice Match Enrolment (Prototype)", standalone)
        self.assertIn("# Voice Learning setup and bridge protocol", standalone)
        self.assertNotIn("Neither is installed or active in this home", standalone)
        self.assertIn("separately approved cutover", standalone)

    def test_entry_point_docs_use_single_combined_repository_without_beta_claim(self):
        for name in ("README.md", "voice_match/DOCS.md"):
            with self.subTest(name=name):
                text = (ROOT / name).read_text()
                self.assertIn(GUIDE, text)
                self.assertIn("BETA_ACCEPTANCE.md", text)
                self.assertIn("standalone", text.lower())


if __name__ == "__main__":
    unittest.main()
