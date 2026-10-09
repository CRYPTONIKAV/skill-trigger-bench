import json

from skill_trigger_bench.lint import lint, referenced_files
from skill_trigger_bench.skills import collect, find_skills, plugin_skill_dirs

from .helpers import SkillDirCase

GOOD = "Summarize CSV files with column types. Use when the user asks what is in a CSV file."


def rules(findings):
    return [f.rule for f in findings]


class LintTests(SkillDirCase):
    def run_lint(self, **kw):
        return lint(find_skills(self.root), **kw)

    def test_clean_skill_has_no_findings(self):
        self.make_skill("csv-summary", "csv-summary", GOOD)
        findings, stats = self.run_lint()
        self.assertEqual(findings, [])
        self.assertEqual(stats["errors"], 0)

    def test_missing_frontmatter(self):
        self.make_skill("x", raw="# no frontmatter\n")
        self.assertEqual(rules(self.run_lint()[0]), ["frontmatter"])

    def test_missing_name_and_description(self):
        self.make_skill("x", extra="license: MIT")
        r = rules(self.run_lint()[0])
        self.assertIn("name-missing", r)
        self.assertIn("description-missing", r)

    def test_name_too_long(self):
        n = "a" * 65
        self.make_skill(n, n, GOOD)
        self.assertIn("name-length", rules(self.run_lint()[0]))

    def test_name_bad_format(self):
        self.make_skill("PDF_Tool", "PDF_Tool", GOOD)
        self.assertIn("name-format", rules(self.run_lint()[0]))

    def test_name_double_hyphen(self):
        self.make_skill("a--b", "a--b", GOOD)
        self.assertIn("name-format", rules(self.run_lint()[0]))

    def test_name_dir_mismatch_is_warning(self):
        self.make_skill("folder", "other-name", GOOD)
        f = [x for x in self.run_lint()[0] if x.rule == "name-dir-mismatch"]
        self.assertEqual(f[0].severity, "warning")

    def test_description_too_long(self):
        self.make_skill("x", "x", "Use when testing. " + "word " * 220)
        self.assertIn("description-length", rules(self.run_lint()[0]))

    def test_description_short(self):
        self.make_skill("x", "x", "Use when x.")
        self.assertIn("description-short", rules(self.run_lint()[0]))

    def test_description_without_when(self):
        self.make_skill("x", "x", "Converts PDF documents into clean Markdown with tables preserved.")
        self.assertIn("description-no-when", rules(self.run_lint()[0]))

    def test_description_with_when_variants(self):
        for i, d in enumerate(
            [
                "Converts PDF documents into Markdown. Use for any PDF the user drops in.",
                "Converts PDF documents into Markdown whenever a PDF shows up in the chat.",
                "Converts PDF documents into Markdown if the user uploads a scanned document.",
                "Triggers on requests to turn PDF documents into Markdown text.",
            ]
        ):
            self.make_skill(f"s{i}", f"s{i}", d)
        self.assertNotIn("description-no-when", rules(self.run_lint(overlap=1.1)[0]))

    def test_compatibility_length(self):
        self.make_skill("x", "x", GOOD, extra="compatibility: " + "y" * 501)
        self.assertIn("compatibility-length", rules(self.run_lint()[0]))

    def test_folded_description_is_read(self):
        self.make_skill(
            "x", raw="---\nname: x\ndescription: >\n  Summarize CSV files.\n  Use when asked about a CSV.\n---\n"
        )
        self.assertEqual(find_skills(self.root)[0].description, "Summarize CSV files. Use when asked about a CSV.")

    def test_body_too_long(self):
        self.make_skill("x", "x", GOOD, body="line\n" * 30)
        self.assertIn("body-too-long", rules(self.run_lint(max_lines=20)[0]))

    def test_missing_link_is_error(self):
        self.make_skill("x", "x", GOOD, body="See [the guide](references/guide.md).\n")
        f = [x for x in self.run_lint()[0] if x.rule == "missing-reference"]
        self.assertEqual(f[0].severity, "error")

    def test_existing_link_is_fine(self):
        d = self.make_skill("x", "x", GOOD, body="See [the guide](references/guide.md#top).\n")
        (d / "references").mkdir()
        (d / "references" / "guide.md").write_text("hi")
        self.assertNotIn("missing-reference", rules(self.run_lint()[0]))

    def test_bare_path_found_in_sibling_skill_is_fine(self):
        self.make_skill("a", "a", GOOD, body="Run `/b` and read `references/shared.md`.\n")
        d = self.make_skill("b", "b", "Bake bread at home. Use when the user wants sourdough tips.")
        (d / "references").mkdir()
        (d / "references" / "shared.md").write_text("hi")
        self.assertNotIn("missing-reference", rules(self.run_lint()[0]))

    def test_bare_path_missing_everywhere_is_warning(self):
        self.make_skill("a", "a", GOOD, body="Run scripts/build.py first.\n")
        f = [x for x in self.run_lint()[0] if x.rule == "missing-reference"]
        self.assertEqual(f[0].severity, "warning")

    def test_urls_and_code_fences_ignored(self):
        refs = referenced_files("[x](https://e.com/a.md) [y](#anchor)\n```\nscripts/in_fence.py\n```\n[z](/abs.md)\n")
        self.assertEqual(refs, [])

    def test_links_in_code_and_placeholders_ignored(self):
        body = (
            "> Also see: [Title](URL) and [notes](path).\n"
            "Use `[x](missing.md)` in your own skill.\n"
            "```python\n"
            "subprocess.Popen(['id'],shell=True,stdout=-1)\n"
            "[a](in_fence.md)\n"
            "```\n"
            "[real](references/real.md)\n"
        )
        self.assertEqual(referenced_files(body), [("references/real.md", True)])

    def test_description_use_during(self):
        self.make_skill("x", "x", "EU AI Act readiness check. Use during AI-system intake or before EU deployment.")
        self.assertNotIn("description-no-when", rules(self.run_lint()[0]))

    def test_duplicate_identical_copies_named(self):
        self.make_skill("one/pdf", "pdf", GOOD)
        self.make_skill("two/pdf", "pdf", GOOD)
        self.make_skill("three/doc", "doc", GOOD)
        self.make_skill("four/doc", "doc", GOOD, body="different\n")
        msgs = {f.skill: f.message for f in self.run_lint()[0] if f.rule == "duplicate-name"}
        self.assertIn("identical copies", msgs["pdf"])
        self.assertIn("share this name", msgs["doc"])

    def test_symlink_loop_does_not_hang(self):
        import os

        self.make_skill("pack/a", "a", GOOD)
        os.symlink("..", self.root / "pack" / "loop")
        os.symlink(self.root / "pack", self.root / "pack-again")
        self.assertEqual([s.name for s in find_skills(self.root)], ["a"])

    def test_template_paths_ignored(self):
        self.assertEqual(referenced_files("[x](references/{name}.md) [y](references/*.md)"), [])

    def test_duplicate_names(self):
        self.make_skill("one/pdf", "pdf", GOOD)
        self.make_skill("two/pdf", "pdf", GOOD)
        r = rules(self.run_lint()[0])
        self.assertIn("duplicate-name", r)
        self.assertNotIn("trigger-overlap", r)

    def test_budget_over(self):
        for i in range(5):
            self.make_skill(f"s{i}", f"s{i}", f"Topic{i} " + f"unique{i} " * 30 + "Use when needed.")
        findings, stats = self.run_lint(budget=500, overlap=1.1)
        f = [x for x in findings if x.rule == "description-budget"]
        self.assertEqual(f[0].severity, "error")
        self.assertGreater(stats["description_chars"], 500)

    def test_budget_near_limit_warns(self):
        self.make_skill("x", "x", GOOD)
        f = [x for x in self.run_lint(budget=len(GOOD) + 10)[0] if x.rule == "description-budget"]
        self.assertEqual(f[0].severity, "warning")

    def test_trigger_overlap_reports_pair(self):
        self.make_skill(
            "resend", "resend", "Send transactional email with the Resend API, webhooks, domains. Use when emailing."
        )
        self.make_skill(
            "resend-cli",
            "resend-cli",
            "Send email with the Resend CLI: webhooks, domains, templates. Use when emailing from a terminal.",
        )
        self.make_skill("bread", "bread", "Bake sourdough bread. Use when the user asks about baking.")
        findings, stats = self.run_lint()
        self.assertEqual(len(stats["overlapping_pairs"]), 1)
        pair = stats["overlapping_pairs"][0]
        self.assertEqual({pair["a"], pair["b"]}, {"resend", "resend-cli"})
        self.assertIn("resend", pair["shared"])

    def test_errors_sorted_first(self):
        self.make_skill("x", "x", "Converts PDF documents into Markdown with tables preserved nicely.")
        self.make_skill("y", extra="license: MIT")
        findings, _ = self.run_lint()
        self.assertEqual(findings[0].severity, "error")


class DiscoveryTests(SkillDirCase):
    def test_single_skill_dir(self):
        d = self.make_skill("x", "x", GOOD)
        self.assertEqual(len(find_skills(d)), 1)

    def test_nested_and_resources_not_scanned(self):
        d = self.make_skill("pack/a", "a", GOOD)
        self.make_skill("pack/b", "b", GOOD)
        (d / "examples" / "inner").mkdir(parents=True)
        (d / "examples" / "inner" / "SKILL.md").write_text("---\nname: inner\n---\n")
        self.assertEqual(sorted(s.name for s in find_skills(self.root)), ["a", "b"])

    def test_collect_dedupes(self):
        self.make_skill("x", "x", GOOD)
        self.assertEqual(len(collect([str(self.root), str(self.root / "x")])), 1)

    def test_missing_dir_is_empty(self):
        self.assertEqual(find_skills(self.root / "nope"), [])

    def test_plugin_dirs_from_manifest(self):
        plug = self.root / "cache" / "acme" / "1.0"
        self.make_skill("cache/acme/1.0/skills/thing", "thing", GOOD)
        (self.root / "plugins").mkdir()
        (self.root / "plugins" / "installed_plugins.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {"acme@market": [{"installPath": str(plug)}], "gone@m": [{"installPath": "/nope"}]},
                }
            )
        )
        self.assertEqual(plugin_skill_dirs(self.root), [("acme", plug / "skills")])

    def test_plugin_manifest_missing(self):
        self.assertEqual(plugin_skill_dirs(self.root), [])
