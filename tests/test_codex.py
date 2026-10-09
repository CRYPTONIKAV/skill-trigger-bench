# Fixtures are hand-written, not recorded from a live run. They follow the `codex exec --json`
# schema in openai/codex codex-rs/exec/src/exec_events.rs and the example stream at
# https://learn.chatgpt.com/docs/non-interactive-mode (thread.started, turn.*, item.*, error).
import subprocess
from pathlib import Path
from unittest import mock

from skill_trigger_bench.cli import build_parser
from skill_trigger_bench.runners import RUNNERS, CodexRunner, RunnerError
from skill_trigger_bench.stream import codex_skill_reads, parse_codex_text

from .helpers import SkillDirCase, fixture


class CodexParseTests(SkillDirCase):
    def test_activation(self):
        t = parse_codex_text(fixture("codex_trigger.jsonl"))
        self.assertTrue(t.finished)
        self.assertFalse(t.is_error)
        self.assertEqual(t.skill_calls, ["csv-summary"])  # started + completed counted once
        self.assertTrue(t.activated("csv-summary"))
        self.assertEqual(t.tool_calls, ["command_execution"])
        self.assertEqual(t.result, "Using the csv-summary skill.")

    def test_no_activation(self):
        t = parse_codex_text(fixture("codex_no_trigger.jsonl"))
        self.assertTrue(t.finished)
        self.assertEqual(t.skill_calls, [])
        self.assertFalse(t.activated("csv-summary"))

    def test_other_skill(self):
        t = parse_codex_text(fixture("codex_other_skill.jsonl"))
        self.assertEqual(t.first_skill(), "bread")
        self.assertFalse(t.activated("csv-summary"))

    def test_folder_mapped_to_frontmatter_name(self):
        t = parse_codex_text(fixture("codex_other_skill.jsonl"), {"bread": "sourdough"})
        self.assertEqual(t.skill_calls, ["sourdough"])

    def test_error(self):
        t = parse_codex_text(fixture("codex_error.jsonl"))
        self.assertTrue(t.is_error)
        self.assertEqual(t.subtype, "turn.failed")
        self.assertIn("401", t.result)

    def test_bad_lines(self):
        t = parse_codex_text("not json\n" + fixture("codex_no_trigger.jsonl"))
        self.assertEqual(t.bad_lines, 1)

    def test_skill_read_regex(self):
        self.assertEqual(codex_skill_reads("cat ~/x/.agents/skills/pdf/SKILL.md"), ["pdf"])
        self.assertEqual(codex_skill_reads("rg SKILL.md"), [])
        self.assertEqual(codex_skill_reads("ls skills/pdf/reference.md"), [])


class CodexRunnerTests(SkillDirCase):
    def _run(self, stdout, code=0):
        skill = self.make_skill("csv", "csv-summary", "Summarize a CSV file.")
        seen = {}

        def fake(cmd, cwd, env, **kw):
            seen.update(cmd=cmd, cwd=Path(cwd), env=env)
            seen["installed"] = (Path(cwd) / ".agents/skills/csv/SKILL.md").is_file()
            return subprocess.CompletedProcess(cmd, code, stdout, "boom")

        with mock.patch("skill_trigger_bench.runners.subprocess.run", side_effect=fake):
            t = CodexRunner().run("hi", [skill])
        return t, seen

    def test_registered_as_agent(self):
        self.assertIs(RUNNERS["codex"], CodexRunner)
        args = build_parser().parse_args(["eval", "x", "--agent", "codex"])
        self.assertEqual(args.runner, "codex")

    def test_sandbox_and_flags(self):
        out = fixture("codex_trigger.jsonl").replace(".agents/skills/csv-summary/", ".agents/skills/csv/")
        t, seen = self._run(out)
        self.assertTrue(seen["installed"])
        self.assertEqual(t.skill_calls, ["csv-summary"])  # folder "csv" mapped to its name
        cmd = seen["cmd"]
        self.assertEqual(cmd[:3], ["codex", "exec", "--json"])
        self.assertIn("read-only", cmd)
        self.assertIn('web_search="disabled"', cmd)
        self.assertEqual(seen["env"]["HOME"], str(seen["cwd"]))
        self.assertFalse(seen["cwd"].exists())  # cleaned up

    def test_error_raises(self):
        with self.assertRaises(RunnerError):
            self._run(fixture("codex_error.jsonl"), code=1)
