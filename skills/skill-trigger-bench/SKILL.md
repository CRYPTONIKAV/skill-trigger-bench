---
name: skill-trigger-bench
description: Check whether Agent Skills (SKILL.md folders) will actually trigger, using the stb CLI. Use when the user writes or edits a skill, asks why a skill isn't being picked up, wants to audit their installed skills for overlap or the description budget, or wants to measure a skill's activation rate.
---

# skill-trigger-bench

`stb` is a CLI. Check it is installed with `stb --version`; if not, install with
`pipx install .` from a clone of the repo (or `uv tool install .`).

## Static checks (free, offline)

Run `stb lint` with no arguments to check everything installed (`~/.claude/skills`,
`.claude/skills`, and installed plugin skills), or pass skill folders:

    stb lint path/to/my-skill
    stb lint --format json

Explain each finding in plain words and propose a concrete fix:
- `description-no-when`: rewrite the description to end with "Use when ..." plus real phrasings.
- `trigger-overlap`: the two descriptions share the listed terms; make each one say what
  it is *not* for, or merge the skills.
- `description-budget`: too many skills are installed for the model to see all of them;
  suggest which ones to uninstall or shorten.
- `missing-reference`: fix the path or add the file.

Edit the SKILL.md only if the user asks you to, then run `stb lint` again.

## Live activation check (costs model calls)

`stb eval <skill-dir>` runs prompts through `claude -p` in a throwaway project that only has
the chosen skills. **Ask the user before running it**, and start small:

    stb eval path/to/my-skill --dry-run          # show generated prompts, no model calls
    stb eval path/to/my-skill --prompts prompts.yaml --model haiku

Do not run `stb eval` on yourself from inside an eval sandbox. Report the trigger rate,
the false-trigger rate, and the prompts that went the wrong way.
