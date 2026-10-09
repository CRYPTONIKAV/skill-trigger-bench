"""Parse `claude -p --output-format stream-json --verbose` transcripts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Transcript:
    loaded_skills: list[str] | None = None  # from the init event, when present
    skill_calls: list[str] = field(default_factory=list)  # in call order
    tool_calls: list[str] = field(default_factory=list)
    result: str | None = None
    finished: bool = False  # a final "result" event was seen
    subtype: str | None = None
    is_error: bool = False
    cost_usd: float | None = None
    bad_lines: int = 0

    def activated(self, skill: str) -> bool:
        return any(skill_matches(call, skill) for call in self.skill_calls)

    def first_skill(self) -> str | None:
        return self.skill_calls[0] if self.skill_calls else None


def skill_matches(called: str, skill: str) -> bool:
    """'pdf' matches 'pdf', 'plugin:pdf' and '/pdf'."""
    called = called.strip().lstrip("/")
    return called == skill or called.rsplit(":", 1)[-1] == skill


def _skill_name_from_input(inp) -> str | None:
    if not isinstance(inp, dict):
        return None
    for key in ("skill", "name", "command", "skill_name"):
        v = inp.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip().split()[0]
    return None


def _content_blocks(event: dict):
    msg = event.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, list):
            return content
    return []


def parse_events(events) -> Transcript:
    t = Transcript()
    for ev in events:
        if not isinstance(ev, dict):
            t.bad_lines += 1
            continue
        typ = ev.get("type")
        if typ == "system" and ev.get("subtype") == "init":
            sk = ev.get("skills")
            if isinstance(sk, list):
                t.loaded_skills = [s if isinstance(s, str) else str(s.get("name", "")) for s in sk]
        elif typ == "assistant":
            for block in _content_blocks(ev):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name", "")
                    t.tool_calls.append(name)
                    if name == "Skill":
                        s = _skill_name_from_input(block.get("input"))
                        if s:
                            t.skill_calls.append(s)
        elif typ == "result":
            t.finished = True
            t.subtype = ev.get("subtype")
            t.result = ev.get("result") if isinstance(ev.get("result"), str) else None
            # running out of turns is expected here (we cap turns low); anything else is a real error
            if t.subtype == "error_max_turns":
                t.is_error = False
            else:
                t.is_error = bool(ev.get("is_error")) or t.subtype not in (None, "success")
            cost = ev.get("total_cost_usd", ev.get("cost_usd"))
            if isinstance(cost, (int, float)):
                t.cost_usd = float(cost)
    return t


def parse_lines(lines) -> Transcript:
    events = []
    bad = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            bad += 1
    t = parse_events(events)
    t.bad_lines += bad
    return t


def parse_text(text: str) -> Transcript:
    return parse_lines(text.splitlines())
