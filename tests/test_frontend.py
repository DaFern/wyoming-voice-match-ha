"""Guard native form methods against HTML named-property clobbering."""

from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import unittest

STATIC = Path(__file__).resolve().parents[1] / "voice_match/rootfs/opt/voice_match/static"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.form_controls = []
        self.in_form = False

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if "id" in values:
            self.ids.add(values["id"])
        if tag == "form":
            self.in_form = True
        elif self.in_form and tag in {"button", "input", "select", "textarea", "fieldset", "output"}:
            self.form_controls.append(values)

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_form = False


class FrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required for launch prototype")
    def test_isolated_learning_launch_contract(self):
        result = subprocess.run(
            [shutil.which("node"), str(Path(__file__).with_name("learning_launch.cjs"))],
            capture_output=True, text=True, timeout=15, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Learning launch prototype checks passed", result.stdout)

    def page(self):
        page = Page()
        page.feed((STATIC / "index.html").read_text())
        return page

    def test_controls_cannot_shadow_native_form_reset(self):
        # Browsers expose controls by id/name on their form. A button whose
        # id is "reset" replaces form.reset with an element, causing the
        # reported "reset is not a function" after saving and on Re-enrol.
        for control in self.page().form_controls:
            for attribute in ("id", "name"):
                self.assertNotEqual(control.get(attribute), "reset", control)

    def test_javascript_static_id_references_exist(self):
        references = set(re.findall(r'\$\("([^"]+)"\)', (STATIC / "app.js").read_text()))
        self.assertEqual(references - self.page().ids, set())

    @unittest.skipUnless(shutil.which("node"), "Node required for renderer execution")
    def test_phrase_renderer_progress_retry_resume_completion_and_safe_text(self):
        result = subprocess.run(
            [shutil.which("node"), str(Path(__file__).with_name("frontend_prompts.cjs"))],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Guided phrase rendering checks passed", result.stdout)

    @unittest.skipUnless(shutil.which("node"), "Node required for pairing UI execution")
    def test_learning_pairing_controls_privacy_roles_and_uncertain_outcomes(self):
        result = subprocess.run(
            [shutil.which("node"), str(Path(__file__).with_name("frontend_learning_pairing.cjs"))],
            capture_output=True, text=True, timeout=15, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Learning pairing controls checks passed", result.stdout)
