"""Static, offline checks for a set of skills."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .similarity import similar_pairs
from .skills import Skill

# Limits from the Agent Skills spec: https://agentskills.io/specification
NAME_MAX = 64
DESCRIPTION_MAX = 1024
COMPATIBILITY_MAX = 500
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Claude Code only shows skill descriptions up to a character budget; skills past it
# are silently left out. ~15k chars per https://blog.fsck.com/2025/12/17/claude-code-skills-not-triggering/
DEFAULT_BUDGET = 15000
# Anthropic's authoring guide suggests keeping SKILL.md under 500 lines.
BODY_MAX_LINES = 500
DEFAULT_OVERLAP = 0.35

WHEN_CUES = re.compile(
    r"\b(use (it |this |this skill )?(when|whenever|for|if|to|on|before|after)|when(ever)?\b|"
    r"if (the )?(user|you)|trigger(s|ed)?|invoke|load (it )?(when|before|for)|applies to|"
    r"for any request|asks? (for|to|about)|mentions?)\b",
    re.I,
)

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass
class Finding:
    rule: str
    severity: str  # error | warning | info
    skill: str
    message: str
    path: str = ""
    other: str = ""

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v != ""}


def _check_frontmatter(s: Skill) -> list[Finding]:
    f = []
    p = str(s.path)
    if s.error:
        return [Finding("frontmatter", "error", s.name, s.error, p)]
    name = s.meta.get("name")
    desc = s.meta.get("description")
    if not isinstance(name, str) or not name.strip():
        f.append(Finding("name-missing", "error", s.name, "frontmatter has no 'name'", p))
    else:
        if len(name) > NAME_MAX:
            f.append(Finding("name-length", "error", name, f"name is {len(name)} chars (max {NAME_MAX})", p))
        if not NAME_RE.match(name):
            f.append(
                Finding(
                    "name-format",
                    "error",
                    name,
                    "name must be lowercase letters, digits and single hyphens",
                    p,
                )
            )
        if name != s.dir.name:
            f.append(
                Finding(
                    "name-dir-mismatch",
                    "warning",
                    name,
                    f"name does not match its folder '{s.dir.name}'",
                    p,
                )
            )
    if not isinstance(desc, str) or not desc.strip():
        f.append(Finding("description-missing", "error", s.name, "frontmatter has no 'description'", p))
        return f
    d = desc.strip()
    if len(d) > DESCRIPTION_MAX:
        f.append(
            Finding(
                "description-length",
                "error",
                s.name,
                f"description is {len(d)} chars (max {DESCRIPTION_MAX})",
                p,
            )
        )
    elif len(d) < 40:
        f.append(
            Finding(
                "description-short",
                "warning",
                s.name,
                f"description is only {len(d)} chars; there is little for the model to match on",
                p,
            )
        )
    if not WHEN_CUES.search(d):
        f.append(
            Finding(
                "description-no-when",
                "warning",
                s.name,
                "description says what the skill does but not when to use it (add 'Use when ...')",
                p,
            )
        )
    if re.search(r"[<>]", d):
        f.append(Finding("description-angle-brackets", "info", s.name, "description contains '<' or '>'", p))
    comp = s.meta.get("compatibility")
    if isinstance(comp, str) and len(comp) > COMPATIBILITY_MAX:
        f.append(
            Finding(
                "compatibility-length",
                "error",
                s.name,
                f"compatibility is {len(comp)} chars (max {COMPATIBILITY_MAX})",
                p,
            )
        )
    return f


LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
PATH_RE = re.compile(r"(?<![\w/.-])((?:references|scripts|assets|reference|templates|examples)/[\w./-]+\.\w+)")


def referenced_files(body: str) -> list[tuple[str, bool]]:
    """(path, is_markdown_link) for each relative file the body points at."""
    refs = []
    in_fence = False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        for m in LINK_RE.finditer(line):
            refs.append((m.group(1), True))
        if not in_fence:
            refs += [(r, False) for r in PATH_RE.findall(line)]
    out, seen = [], set()
    for r, is_link in refs:
        r = r.split("#", 1)[0].strip("`'\"")
        if not r or re.match(r"^[a-z][a-z0-9+.-]*:", r, re.I) or r.startswith(("/", "~", "$")):
            continue
        if "{" in r or "*" in r or "<" in r:
            continue
        if r not in seen:
            seen.add(r)
            out.append((r, is_link))
    return out


def _check_body(s: Skill, max_lines: int, siblings: list[Path] = ()) -> list[Finding]:
    if s.error and not s.body:
        return []
    f = []
    n = len(s.body.splitlines())
    if n > max_lines:
        f.append(
            Finding(
                "body-too-long",
                "warning",
                s.name,
                f"SKILL.md body is {n} lines (suggested max {max_lines}); move detail into reference files",
                str(s.path),
            )
        )
    for ref, is_link in referenced_files(s.body):
        if (s.dir / ref).exists():
            continue
        if is_link:
            f.append(
                Finding(
                    "missing-reference", "error", s.name, f"links to '{ref}' but that file does not exist", str(s.path)
                )
            )
        elif not any((d / ref).exists() for d in siblings):
            # a bare path in prose may point into another skill; only warn when no skill has it
            f.append(
                Finding(
                    "missing-reference",
                    "warning",
                    s.name,
                    f"mentions '{ref}' but no installed skill has that file",
                    str(s.path),
                )
            )
    return f


def lint(
    skills: list[Skill],
    budget: int = DEFAULT_BUDGET,
    overlap: float = DEFAULT_OVERLAP,
    max_lines: int = BODY_MAX_LINES,
) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    dirs = [s.dir for s in skills]
    for s in skills:
        findings += _check_frontmatter(s)
        findings += _check_body(s, max_lines, [d for d in dirs if d != s.dir])

    # duplicate names: the agent can only pick one
    by_name: dict[str, list[Skill]] = {}
    for s in skills:
        by_name.setdefault(s.name, []).append(s)
    for name, group in by_name.items():
        if len(group) > 1:
            where = ", ".join(sorted({g.source for g in group}))
            findings.append(
                Finding(
                    "duplicate-name",
                    "error",
                    name,
                    f"{len(group)} skills share this name ({where})",
                    str(group[0].path),
                )
            )

    # description budget across the whole set
    usable = [s for s in skills if s.description]
    total = sum(len(s.name) + len(s.description) for s in usable)
    if total > budget:
        running, cut = 0, []
        for s in usable:
            running += len(s.name) + len(s.description)
            if running > budget:
                cut.append(s.name)
        findings.append(
            Finding(
                "description-budget",
                "error",
                "*",
                f"{len(usable)} skill descriptions total {total} chars, over the ~{budget} char budget; "
                f"roughly {len(cut)} of them may never be shown to the model",
            )
        )
    elif total > budget * 0.8:
        findings.append(
            Finding(
                "description-budget",
                "warning",
                "*",
                f"skill descriptions total {total} chars, {total * 100 // budget}% of the ~{budget} char budget",
            )
        )

    # trigger overlap between descriptions
    pairs = []
    if len(usable) > 1:
        for i, j, score, terms in similar_pairs([s.description for s in usable], overlap):
            a, b = usable[i], usable[j]
            if a.name == b.name:
                continue  # already reported as duplicate-name
            pairs.append({"a": a.name, "b": b.name, "score": round(score, 3), "shared": terms})
            findings.append(
                Finding(
                    "trigger-overlap",
                    "warning",
                    a.name,
                    f"description overlaps with '{b.name}' (cosine {score:.2f}; shared: {', '.join(terms)})",
                    str(a.path),
                    other=b.name,
                )
            )

    findings.sort(key=lambda x: (SEVERITY_ORDER[x.severity], x.rule, x.skill))
    stats = {
        "skills": len(skills),
        "description_chars": total,
        "budget": budget,
        "overlap_threshold": overlap,
        "overlapping_pairs": pairs,
        "errors": sum(1 for x in findings if x.severity == "error"),
        "warnings": sum(1 for x in findings if x.severity == "warning"),
    }
    return findings, stats


def relpath(p: str) -> str:
    try:
        return "~/" + str(Path(p).relative_to(Path.home()))
    except ValueError:
        return p
