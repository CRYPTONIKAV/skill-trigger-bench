# State of public skills, October 2026

I ran `stb lint` over the most-starred public skill repos to see what the static checks
find on real packs, and what happens when you install several of them at once. Everything
here is offline: no model calls, nothing from the repos was executed.

Short version: the single-purpose packs are in good shape. Problems show up in two places:
very large packs, and installing more than one pack. Almost all of it is fixable with a
text edit.

## How this was run

Shallow clones taken on 2026-10-09:

| repo | commit |
|---|---|
| anthropics/skills | 9d63080 |
| obra/superpowers | 8ca22db |
| ComposioHQ/awesome-claude-skills | be2a406 |
| alirezarezvani/claude-skills | 19392f7 |
| Jeffallan/claude-skills | 1be15d8 |
| SnailSploit/Claude-Red | 739512a |
| nidhinjs/prompt-master | 2bd9251 |
| SawyerHood/dev-browser | a25e767 |

Then `stb lint --format json <repo>` for each one, and once with all of them together.
Some things to keep in mind:

- `stb` skips dot-folders. alirezarezvani/claude-skills keeps per-agent mirrors in
  `.gemini/`, `.codex/` and so on, so those aren't counted. 14 of its skills also exist
  twice outside the dot-folders, as identical copies (plugin layout plus a flat
  `skills/` folder). They're counted twice below.
- awesome-claude-skills is mostly a list, but it also ships real skills: 32 hand-written
  ones at the top level and 832 generated Composio toolkit skills in `composio-skills/`.
  The two halves look very different, so I split them where it matters.
- "Description chars" is name + description summed over the pack. That's what counts
  against the listing budget.
- "Missing when" means the description never says when to use the skill (no "use when",
  "use for", "whenever", "triggers on" and similar). It's a regex, so read it as a hint.
- "Overlapping pairs" is TF-IDF cosine ≥ 0.35 between two descriptions. It's lexical. It
  catches obvious collisions, misses paraphrases, and sometimes flags pairs that are
  meant to sit next to each other.
- "Broken refs" only counts markdown links to relative files that don't exist. Bare
  paths in prose (often examples, like `scripts/tool.sh` in a guide about writing skills)
  aren't counted.
- "Spec errors" are hard failures against the
  [Agent Skills spec](https://agentskills.io/specification): missing frontmatter, a name
  that isn't lowercase-hyphen, a description over 1024 chars.

Running this turned up four false positives in `stb`, which are fixed now: links inside
code blocks and inline code, placeholder links like `[Title](URL)`, "Use during ..." not
counting as a when-clause, and a hang on symlink loops.

## Per repo

| repo | skills | description chars | missing "when" | overlapping pairs | broken refs | bodies > 500 lines | spec errors |
|---|---:|---:|---:|---:|---:|---:|---:|
| obra/superpowers | 15 | 2,615 | 0% | 1 | 0 | 2 | 0 |
| anthropics/skills | 20 | 9,696 | 10% | 1 | 0 | 1 | 1 |
| ComposioHQ/awesome-claude-skills (top level) | 32 | 8,306 | 50% | 2 | 0 | 2 | 0 |
| ComposioHQ/awesome-claude-skills (`composio-skills/`) | 832 | 103,384 | 100% | 1,862 | 0 | 0 | 92 |
| alirezarezvani/claude-skills | 387 | 182,927 | 0% | 51 | 2 | 3 | 1 |
| Jeffallan/claude-skills | 67 | 30,376 | 0% | 2 | 0 | 0 | 0 |
| SnailSploit/Claude-Red | 79 | 43,758 | 27% | 1 | 2 | 41 | 46 |
| nidhinjs/prompt-master | 1 | 346 | 0% | 0 | 0 | 0 | 0 |
| SawyerHood/dev-browser | 1 | 436 | 0% | 0 | 0 | 0 | 0 |

Notes per repo:

- **obra/superpowers** is the cleanest of the big ones. 15 short descriptions, all with a
  clear trigger. The one overlap is `executing-plans` / `subagent-driven-development`,
  two ways to run a plan, so some overlap is expected there.
- **anthropics/skills**: `claude-api` has a 1,068-char description, a bit over the
  spec's 1,024, and that looks deliberate (it's a detailed TRIGGER/SKIP block).
  `theme-factory` and `webapp-testing` describe what they do but not when to use them.
- **ComposioHQ top level**: half the descriptions have no when-clause. Several of these
  skills are copies of anthropics/skills (see below).
- **ComposioHQ `composio-skills/`**: these are generated, so one template fix fixes all
  of them. 92 have names like `Apify Automation` (spaces and capitals) or start with a
  hyphen (`-21risk-automation`), which the spec doesn't allow. None of the descriptions
  say when to use the skill. Some toolkits show up twice under two spellings, e.g.
  `SurveyMonkey Automation` and `survey_monkey-automation`.
- **alirezarezvani/claude-skills** is huge (387 skills, 183k description chars), but
  every description has a when-clause, which is good discipline at that size. Two links
  are written relative to the repo root instead of the file, so they 404 even on GitHub.
- **Jeffallan/claude-skills** is clean apart from size: 67 skills, about 2x the budget
  on its own.
- **SnailSploit/Claude-Red**: 28 SKILL.md files have no YAML frontmatter at all, so an
  agent can't list them. 18 descriptions are over 1,024 chars, and 41 bodies are over
  500 lines.
- The two single-skill repos are fine. prompt-master gets a name/folder mismatch, but
  only because of the folder I cloned into, so I left it out.

## The worst overlaps

These are the pairs most likely to compete for the same prompt, across all 8 repos
installed together. The generated Composio toolkit pairs are left out (more on those
below).

| score | pair | why |
|---:|---|---|
| 1.00 | `artifacts-builder` (Composio) / `web-artifacts-builder` (anthropics) | same description, renamed |
| 0.74 | `connect` / `connect-apps` (both Composio) | two entry points for the same thing |
| 0.68 | `java-architect` / `spring-boot-engineer` (Jeffallan) | Spring Boot, JPA, WebFlux in both |
| 0.61 | `dev-browser` (SawyerHood) / `browser-automation` (alirezarezvani) | browse, fill, screenshot |
| 0.60 | `internal-comms` (anthropics) / `team-communications` (alirezarezvani) | internal updates and reports |
| 0.58 | `general-counsel-advisor` / `gc-review` (alirezarezvani) | advisor and its review command |
| 0.56 | `generate` / `pw-init` (alirezarezvani, playwright-pro) | Playwright e2e setup |
| 0.52 | `chief-data-officer-advisor` / `cdo-review` (alirezarezvani) | same pattern as the GC pair |
| 0.52 | `architecture-designer` (Jeffallan) / `senior-architect` (alirezarezvani) | ADRs, diagrams, scalability |
| 0.51 | `form-cro` / `signup-flow-cro` (alirezarezvani) | signup form friction |

Within one pack, a pair like `gc-review` + `general-counsel-advisor` may be intentional
(a slash command next to its advisor). The usual fix is still the same: one sentence in
each description saying when to pick it over the other.

The generated Composio skills have the highest raw overlap count (1,862 pairs). Top
scorers are `Clockify` / `Toggl` (0.76) and `Harvest` / `Toggl` (0.58). Each one is a
different product, but the shared template ("Automate ... tasks via Rube MCP (Composio)")
makes them look alike to a lexical check. Putting the product name first and moving the
template text out of the description would remove most of that.

## Installing the top 3 together

Claude Code lists skill descriptions within a budget. Skills past it are silently left
out of the list the model sees. The figure people use is about 15,000 characters. That
number comes from a blog post
([fsck.com, Dec 2025](https://blog.fsck.com/2025/12/17/claude-code-skills-not-triggering/)),
not from Anthropic's source or docs, and it may have changed since. Treat everything
below as relative, not exact.

Top 3 by stars: obra/superpowers, anthropics/skills, ComposioHQ/awesome-claude-skills.

| install | skills | description chars | vs ~15k |
|---|---:|---:|---:|
| superpowers + anthropics | 35 | 12,311 | 82%, fits |
| + Composio top level only | 67 | 20,617 | 137% |
| + all of Composio | 899 | 124,001 | about 8x |

- superpowers and anthropics/skills fit together with some room left. Most people
  probably have this setup.
- Adding Composio's hand-written skills goes over the budget. It also adds **13 name
  clashes**, because Composio ships its own copies of `docx`, `pdf`, `pptx`, `xlsx`,
  `skill-creator`, `mcp-builder`, `canvas-design` and others. Six are byte-identical
  to anthropics/skills. The other seven have drifted, so you get two different skills with the same
  name and the agent can only pick one.
- Adding all of `composio-skills/` puts the set at roughly 8x the budget. By `stb`'s
  count, about 848 of 899 descriptions would never be shown.

For scale: all 8 repos together are 1,434 skills and 381,844 description chars. Nobody
should install that, but it shows how fast a few "install the whole pack" steps add up.

## What would help

None of this needs a rewrite:

- **Packs with generated skills**: fix the template once (spec-valid names, a "Use when
  ..." clause, the product name up front).
- **Mega-packs**: say in the README that the pack is meant to be installed per category,
  not all at once. alirezarezvani and Jeffallan already split into plugins, so this is
  mostly documentation.
- **Packs that vendor other packs' skills**: rename them, or drop them and link to the
  source, so users don't end up with two `pdf` skills.
- **Everyone**: run a linter in CI. `stb lint --format json` works, and so do
  `/skill-doctor` and `claude plugin eval` if you're Claude-only.

To reproduce: clone the repos at the commits above and run `stb lint --format json <dir>`.
