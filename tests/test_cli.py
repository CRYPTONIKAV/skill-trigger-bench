import contextlib
import io
import json

from skill_trigger_bench.cli import main

from .helpers import SkillDirCase

GOOD = "Summarize CSV files with column types. Use when the user asks what is in a CSV file."


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTests(SkillDirCase):
    def test_lint_clean_exit_zero(self):
        self.make_skill("csv-summary", "csv-summary", GOOD)
        code, out, _ = run(["lint", str(self.root)])
        self.assertEqual(code, 0)
        self.assertIn("0 errors, 0 warnings", out)

    def test_lint_error_exit_one(self):
        self.make_skill("x", extra="license: MIT")
        self.assertEqual(run(["lint", str(self.root)])[0], 1)

    def test_strict_fails_on_warnings(self):
        self.make_skill("x", "x", "Converts PDF documents into clean Markdown text output.")
        self.assertEqual(run(["lint", str(self.root)])[0], 0)
        self.assertEqual(run(["lint", "--strict", str(self.root)])[0], 1)

    def test_ignore_rule(self):
        self.make_skill("x", "x", "Converts PDF documents into clean Markdown text output.")
        code, out, _ = run(["lint", "--strict", "--ignore", "description-no-when", str(self.root)])
        self.assertEqual(code, 0)

    def test_json_output(self):
        self.make_skill("csv-summary", "csv-summary", GOOD)
        code, out, _ = run(["lint", "--format", "json", str(self.root)])
        data = json.loads(out)
        self.assertTrue(data["ok"])
        self.assertEqual(data["skills"][0]["name"], "csv-summary")
        self.assertEqual(data["findings"], [])

    def test_github_format_error(self):
        self.make_skill("x", extra="license: MIT")
        text_code, _, _ = run(["lint", str(self.root)])
        code, out, _ = run(["lint", "--format", "github", str(self.root)])
        self.assertEqual(code, text_code)
        self.assertEqual(code, 1)
        lines = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertTrue(lines)
        self.assertTrue(
            any(
                ln.startswith("::error file=")
                and "title=description-missing::" in ln
                and "frontmatter has no 'description'" in ln
                for ln in lines
            )
        )

    def test_github_format_warning_notice_and_pathless(self):
        self.make_skill("csv-summary", "csv-summary", GOOD + " <tag>")
        code, out, _ = run(["lint", "--format", "github", "--budget", "10", str(self.root)])
        self.assertEqual(code, 1)
        lines = out.splitlines()
        notices = [ln for ln in lines if ln.startswith("::notice file=") and "title=description-angle-brackets::" in ln]
        self.assertTrue(notices)
        pathless = [ln for ln in lines if "title=description-budget::" in ln]
        self.assertTrue(pathless)
        for ln in pathless:
            self.assertNotIn("file=", ln)

    def test_github_format_clean_exit_zero(self):
        self.make_skill("csv-summary", "csv-summary", GOOD)
        text_code, _, _ = run(["lint", str(self.root)])
        code, out, _ = run(["lint", "--format", "github", str(self.root)])
        self.assertEqual(code, text_code)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")

    def test_github_format_escapes_workflow_command_syntax(self):
        from skill_trigger_bench.cli import _github_escape_data, _github_escape_prop

        # a newline or % in a message would otherwise end or corrupt the annotation
        self.assertEqual(_github_escape_data("50% done\nnext"), "50%25 done%0Anext")
        # : and , separate properties, so they must be escaped inside file= and title=
        self.assertEqual(_github_escape_prop("a:b,c"), "a%3Ab%2Cc")

    def test_no_skills_in_explicit_path(self):
        self.assertEqual(run(["lint", str(self.root / "empty")])[0], 2)

    def test_eval_dry_run_needs_no_model(self):
        d = self.make_skill("csv-summary", "csv-summary", GOOD)
        code, out, _ = run(["eval", str(d), "--dry-run", "-n", "3"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)["should_not_trigger"]), 3)

    def test_eval_rejects_broken_skill(self):
        d = self.make_skill("x", raw="nothing")
        self.assertEqual(run(["eval", str(d), "--dry-run"])[0], 2)

    def test_eval_max_prompts_cap(self):
        d = self.make_skill("csv-summary", "csv-summary", GOOD)
        code, _, err = run(["eval", str(d), "-n", "5", "--max-prompts", "2", "--runner", "claude"])
        self.assertEqual(code, 2)
