"""Static reading guidance, indexed by saved audio rather than recording attempts."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "voice_match/rootfs/opt/voice_match"))
from enrollment_prompts import PHRASES, prompt_for_sample


class PromptTests(unittest.TestCase):
    def test_thirty_distinct_natural_length_phrases(self):
        self.assertEqual(len(PHRASES), 30)
        self.assertEqual(len(set(PHRASES)), 30)
        for phrase in PHRASES:
            self.assertIsInstance(phrase, str)
            self.assertGreaterEqual(len(phrase.split()), 12, phrase)
            self.assertLessEqual(len(phrase.split()), 18, phrase)

    def test_saved_count_selects_phrase_and_completion_has_no_more_prompt(self):
        for count, phrase in enumerate(PHRASES):
            self.assertEqual(prompt_for_sample(count, 30), phrase)
        self.assertIsNone(prompt_for_sample(30, 30))
        self.assertIsNone(prompt_for_sample(31, 30))

    def test_existing_nondefault_sample_targets_are_preserved(self):
        self.assertEqual(prompt_for_sample(0, 1), PHRASES[0])
        self.assertIsNone(prompt_for_sample(1, 1))
        self.assertEqual(prompt_for_sample(30, 100), PHRASES[0])
        self.assertEqual(prompt_for_sample(99, 100), PHRASES[9])
        self.assertIsNone(prompt_for_sample(100, 100))

    def test_invalid_counts_are_not_used_to_index_phrases(self):
        for count, target in ((-1, 30), (0, 0), (0, 101), (True, 30), (0, "30")):
            with self.subTest(count=count, target=target), self.assertRaises(ValueError):
                prompt_for_sample(count, target)
