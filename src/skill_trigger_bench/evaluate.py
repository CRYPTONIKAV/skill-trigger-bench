"""Run a prompt set against one skill and score it."""

from __future__ import annotations

from dataclasses import dataclass, field

from .prompts import PromptSet
from .runners import Runner, RunnerError
from .skills import Skill


@dataclass
class PromptResult:
    prompt: str
    expected: bool
    triggered: bool | None  # None = the run failed
    skill_calls: list[str] = field(default_factory=list)
    error: str | None = None
    cost_usd: float | None = None


@dataclass
class EvalReport:
    skill: str
    runner: str
    results: list[PromptResult]
    skill_not_loaded: bool = False

    def _rate(self, expected: bool) -> float | None:
        done = [r for r in self.results if r.expected is expected and r.triggered is not None]
        if not done:
            return None
        return sum(1 for r in done if r.triggered) / len(done)

    @property
    def trigger_rate(self) -> float | None:
        return self._rate(True)

    @property
    def false_trigger_rate(self) -> float | None:
        return self._rate(False)

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.triggered is None)

    @property
    def cost_usd(self) -> float:
        return sum(r.cost_usd or 0.0 for r in self.results)

    def passed(self, min_trigger: float, max_false: float) -> bool:
        tr, fr = self.trigger_rate, self.false_trigger_rate
        if self.errors or self.skill_not_loaded:
            return False
        return (tr is None or tr >= min_trigger) and (fr is None or fr <= max_false)

    def to_dict(self) -> dict:
        return {
            "skill": self.skill,
            "runner": self.runner,
            "trigger_rate": self.trigger_rate,
            "false_trigger_rate": self.false_trigger_rate,
            "errors": self.errors,
            "skill_not_loaded": self.skill_not_loaded,
            "cost_usd": round(self.cost_usd, 4),
            "results": [r.__dict__ for r in self.results],
        }


def run_eval(skill: Skill, installed: list[Skill], prompts: PromptSet, runner: Runner, progress=None) -> EvalReport:
    """`installed` is every skill placed in the sandbox (the target plus any neighbours)."""
    dirs = []
    for s in [skill, *installed]:
        if s.dir not in dirs:
            dirs.append(s.dir)
    cases = [(p, True) for p in prompts.should_trigger] + [(p, False) for p in prompts.should_not_trigger]
    results = []
    not_loaded = False
    for i, (prompt, expected) in enumerate(cases, 1):
        try:
            t = runner.run(prompt, dirs)
        except RunnerError as e:
            results.append(PromptResult(prompt, expected, None, error=str(e)))
        else:
            if t.loaded_skills is not None and not any(
                n == skill.name or n.endswith(":" + skill.name) for n in t.loaded_skills
            ):
                not_loaded = True
            results.append(PromptResult(prompt, expected, t.activated(skill.name), t.skill_calls, cost_usd=t.cost_usd))
        if progress:
            progress(i, len(cases), results[-1])
    return EvalReport(skill.name, runner.name, results, not_loaded)
