import tempfile
import unittest
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class SkillDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def make_skill(self, folder, name=None, description=None, body="# Body\n", extra="", raw=None):
        d = self.root / folder
        d.mkdir(parents=True, exist_ok=True)
        if raw is None:
            lines = ["---"]
            if name is not None:
                lines.append(f"name: {name}")
            if description is not None:
                lines.append(f"description: {description}")
            if extra:
                lines.append(extra.rstrip("\n"))
            lines.append("---")
            raw = "\n".join(lines) + "\n" + body
        (d / "SKILL.md").write_text(raw, encoding="utf-8")
        return d
