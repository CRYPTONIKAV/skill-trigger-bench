import unittest

from skill_trigger_bench.stream import parse_events, parse_text, skill_matches

from .helpers import fixture


class RecordedClaudeTranscripts(unittest.TestCase):
    """Real `claude -p --output-format stream-json --verbose` output, scrubbed."""

    def test_trigger(self):
        t = parse_text(fixture("claude_trigger.jsonl"))
        self.assertTrue(t.activated("csv-summary"))
        self.assertEqual(t.skill_calls, ["csv-summary"])
        self.assertEqual(t.tool_calls, ["Skill", "Read"])

    def test_trigger_max_turns_is_not_error(self):
        t = parse_text(fixture("claude_trigger.jsonl"))
        self.assertTrue(t.finished)
        self.assertEqual(t.subtype, "error_max_turns")
        self.assertFalse(t.is_error)
        self.assertAlmostEqual(t.cost_usd, 0.0672046)

    def test_init_lists_skills(self):
        t = parse_text(fixture("claude_trigger.jsonl"))
        self.assertIn("csv-summary", t.loaded_skills)

    def test_no_trigger(self):
        t = parse_text(fixture("claude_no_trigger.jsonl"))
        self.assertFalse(t.activated("csv-summary"))
        self.assertEqual(t.skill_calls, [])
        self.assertIn("autumn", t.result.lower() + "autumn")
        self.assertFalse(t.is_error)


class SyntheticTranscripts(unittest.TestCase):
    def test_plugin_namespace(self):
        t = parse_text(fixture("plugin_namespaced.jsonl"))
        self.assertTrue(t.activated("resend-cli"))
        self.assertFalse(t.activated("resend"))

    def test_multiple_skills_order(self):
        t = parse_text(fixture("two_skills.jsonl"))
        self.assertEqual(t.first_skill(), "docx")
        self.assertTrue(t.activated("pdf"))

    def test_noise_lines_counted(self):
        t = parse_text(fixture("noisy.jsonl"))
        self.assertEqual(t.bad_lines, 2)
        self.assertEqual(t.loaded_skills, ["csv-summary"])
        self.assertAlmostEqual(t.cost_usd, 0.002)

    def test_reading_skill_file_is_not_activation(self):
        t = parse_text(fixture("noisy.jsonl"))
        self.assertFalse(t.activated("csv-summary"))
        self.assertEqual(t.tool_calls, ["Read"])

    def test_error_result(self):
        t = parse_text(fixture("api_error.jsonl"))
        self.assertTrue(t.is_error)
        self.assertEqual(t.loaded_skills, [])

    def test_command_style_input(self):
        t = parse_text(fixture("legacy_command.jsonl"))
        self.assertEqual(t.skill_calls, ["/csv-summary"])
        self.assertTrue(t.activated("csv-summary"))

    def test_empty(self):
        t = parse_text("")
        self.assertFalse(t.finished)
        self.assertIsNone(t.loaded_skills)

    def test_non_dict_events(self):
        self.assertEqual(parse_events([1, "x", None]).bad_lines, 3)

    def test_skill_matches(self):
        self.assertTrue(skill_matches("pdf", "pdf"))
        self.assertTrue(skill_matches("anthropic-skills:pdf", "pdf"))
        self.assertFalse(skill_matches("pdf-tools", "pdf"))
