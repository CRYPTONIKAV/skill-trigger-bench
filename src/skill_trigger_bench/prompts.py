"""Eval prompt sets: loaded from a file, or generated from the skill descriptions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import load_yaml
from .similarity import tokens
from .skills import Skill


@dataclass
class PromptSet:
    should_trigger: list[str] = field(default_factory=list)
    should_not_trigger: list[str] = field(default_factory=list)
    generated: bool = False


class PromptFileError(ValueError):
    pass


def _strings(v, key) -> list[str]:
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise PromptFileError(f"'{key}' must be a list of strings")
    return [x.strip() for x in v if x.strip()]


def load_prompt_file(path: Path) -> PromptSet:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix == ".json" else load_yaml(text)
    if not isinstance(data, dict):
        raise PromptFileError("prompt file must be a mapping with should_trigger / should_not_trigger")
    ps = PromptSet(
        _strings(data.get("should_trigger"), "should_trigger"),
        _strings(data.get("should_not_trigger"), "should_not_trigger"),
    )
    if not ps.should_trigger and not ps.should_not_trigger:
        raise PromptFileError("prompt file has no prompts")
    return ps


QUOTED = re.compile(r"[\"“']([^\"”']{4,80})[\"”']")

GENERIC_NEGATIVES = [
    "What's the capital of Australia?",
    "Rename the variable `tmp` to `total` in this snippet: tmp = a + b; print(tmp)",
    "Explain the difference between a list and a tuple in Python in two sentences.",
    "Write a haiku about autumn rain.",
    "How many seconds are there in a week?",
]


def _phrases(desc: str) -> list[str]:
    """Pull 'task-like' phrases out of a description: quoted examples first, then clauses."""
    out = [m.strip() for m in QUOTED.findall(desc)]
    m = re.search(r"\b(?:use|load|invoke)[^.]*?\b(?:when|for|to)\b(.*?)(?:\.|$)", desc, re.I | re.S)
    if m:
        for part in re.split(r",|;|\bor\b", m.group(1)):
            part = part.strip(" -—:()")
            if 3 <= len(part.split()) <= 14:
                out.append(part)
    first = re.split(r"(?<=[.!?])\s", desc.strip(), maxsplit=1)[0].rstrip(".")
    if first:
        out.append(first)
    seen, uniq = set(), []
    for p in out:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq


def generate(skill: Skill, others: list[Skill], n: int = 5) -> PromptSet:
    """Template prompts. Crude on purpose: write a prompt file for anything you care about."""
    templates = [
        "{p}",
        "Can you help me with this: {p}",
        "I need to {p_lower}. Where do I start?",
        "Please {p_lower} for this project.",
        "Quick one: {p_lower}?",
    ]
    pos = []
    for i, phrase in enumerate(_phrases(skill.description)):
        t = templates[i % len(templates)]
        lower = phrase[0].lower() + phrase[1:]
        lower = re.sub(r"^(when |for |to |if )", "", lower, flags=re.I)
        pos.append(t.format(p=phrase, p_lower=lower))
        if len(pos) >= n:
            break
    if not pos:
        kw = " ".join(tokens(skill.description)[:6]) or skill.name.replace("-", " ")
        pos.append(f"Help me with {kw}.")

    neg = []
    own = set(tokens(skill.description))
    for o in others:
        if o.name == skill.name or not o.description:
            continue
        if len(own & set(tokens(o.description))) <= 2:
            # the other skill's first sentence reads like a real request for a different job
            first = re.split(r"(?<=[.!?])\s", o.description.strip(), maxsplit=1)[0].rstrip(".")
            if first:
                neg.append(first)
        if len(neg) >= n // 2 + 1:
            break
    for g in GENERIC_NEGATIVES:
        if len(neg) >= n:
            break
        neg.append(g)
    return PromptSet(pos[:n], neg[:n], generated=True)
