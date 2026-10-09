"""Runners execute one prompt in a sandbox and return a parsed transcript.

To add an agent (Codex, Gemini CLI, ...), subclass Runner, implement `run`, and
register it in RUNNERS.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .stream import Transcript, parse_text


class RunnerError(RuntimeError):
    pass


@dataclass
class Runner:
    model: str | None = None
    timeout: int = 180
    extra_args: list[str] = field(default_factory=list)
    name = "base"

    def available(self) -> bool:
        raise NotImplementedError

    def run(self, prompt: str, skill_dirs: list[Path]) -> Transcript:
        raise NotImplementedError

    @staticmethod
    def make_sandbox(skill_dirs: list[Path], layout: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix="stb-"))
        dest = root / layout
        dest.mkdir(parents=True)
        for d in skill_dirs:
            shutil.copytree(d, dest / d.name, symlinks=False, dirs_exist_ok=True)
        return root


# Tools that could change anything or cost a lot are turned off; the run only needs
# to show whether the model reaches for the Skill tool.
CLAUDE_BLOCKED_TOOLS = [
    "Bash",
    "Edit",
    "Write",
    "NotebookEdit",
    "WebFetch",
    "WebSearch",
    "Task",
    "Agent",
]


@dataclass
class ClaudeRunner(Runner):
    binary: str = "claude"
    max_turns: int = 2
    name = "claude"

    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def command(self, prompt: str) -> list[str]:
        cmd = [
            self.binary,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--max-turns",
            str(self.max_turns),
            # only the sandbox project's settings and skills; ignores ~/.claude skills and plugins
            "--setting-sources",
            "project",
            "--disallowedTools",
            ",".join(CLAUDE_BLOCKED_TOOLS),
        ]
        if self.model:
            cmd += ["--model", self.model]
        return cmd + self.extra_args

    def run(self, prompt: str, skill_dirs: list[Path]) -> Transcript:
        sandbox = self.make_sandbox(skill_dirs, ".claude/skills")
        try:
            proc = subprocess.run(
                self.command(prompt),
                cwd=sandbox,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as e:
            raise RunnerError(f"claude timed out after {self.timeout}s") from e
        except OSError as e:
            raise RunnerError(f"could not start {self.binary}: {e}") from e
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)
        t = parse_text(proc.stdout)
        if t.is_error or (proc.returncode != 0 and not t.finished):
            raise RunnerError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:300]}")
        return t


@dataclass
class ReplayRunner(Runner):
    """Replays recorded transcripts; used by tests and for offline re-scoring."""

    transcripts: list[str] = field(default_factory=list)
    name = "replay"

    def available(self) -> bool:
        return True

    def run(self, prompt: str, skill_dirs: list[Path]) -> Transcript:
        if not self.transcripts:
            raise RunnerError("replay runner ran out of transcripts")
        return parse_text(self.transcripts.pop(0))


RUNNERS: dict[str, type[Runner]] = {"claude": ClaudeRunner}
