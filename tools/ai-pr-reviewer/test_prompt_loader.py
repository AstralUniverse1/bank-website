import unittest

from prompt_loader import load_prompt


class PromptLoaderTests(unittest.TestCase):
    def test_loads_known_prompt(self):
        self.assertIn("You are a PR QA reviewer.", load_prompt("qa_review"))

    def test_rejects_path_traversal_prompt_name(self):
        with self.assertRaisesRegex(ValueError, "prompt name"):
            load_prompt("../session summery")

    def test_rejects_prompt_name_with_path_separator(self):
        with self.assertRaisesRegex(ValueError, "prompt name"):
            load_prompt("nested/prompt")


if __name__ == "__main__":
    unittest.main()
