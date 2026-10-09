"""Finding and loading SKILL.md folders."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import FrontmatterError, load_yaml, split_frontmatter


@dataclass
class Skill:
    path: Path  # the SKILL.md file
    source: str = "dir"  # "user", "project", "plugin:<name>", or "dir"
    meta: dict = field(default_factory=dict)
    body: str = ""
    body_start_line: int = 1
    error: str | None = None

    @property
    def dir(self) -> Path:
        return self.path.parent

    @property
    def name(self) -> str:
        n = self.meta.get("name")
        return n if isinstance(n, str) and n else self.dir.name

    @property
    def description(self) -> str:
        d = self.meta.get("description")
        return d.strip() if isinstance(d, str) else ""


def load_skill(skill_md: Path, source: str = "dir") -> Skill:
    skill = Skill(path=skill_md, source=source)
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        skill.error = f"cannot read file: {e}"
        return skill
    try:
        fm, body, start = split_frontmatter(text)
        skill.body, skill.body_start_line = body, start
        if fm is None:
            skill.error = "no YAML frontmatter (file must start with '---')"
            return skill
        meta = load_yaml(fm)
        if meta is None:
            meta = {}
        if not isinstance(meta, dict):
            skill.error = "frontmatter is not a key/value mapping"
            return skill
        skill.meta = meta
    except FrontmatterError as e:
        skill.error = f"invalid frontmatter: {e}"
    return skill


def find_skills(root: Path, source: str = "dir") -> list[Skill]:
    """A dir that is itself a skill, or a dir of skill folders (searched one level, then deeper)."""
    root = root.expanduser()
    if root.is_file() and root.name == "SKILL.md":
        return [load_skill(root, source)]
    if (root / "SKILL.md").is_file():
        return [load_skill(root / "SKILL.md", source)]
    if not root.is_dir():
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d != "node_modules")
        if "SKILL.md" in filenames:
            found.append(load_skill(Path(dirpath) / "SKILL.md", source))
            dirnames[:] = []  # a skill's own subfolders are its resources
    return found


def plugin_skill_dirs(claude_home: Path) -> list[tuple[str, Path]]:
    """Skill dirs of the plugins Claude Code currently has installed (not every cached version)."""
    manifest = claude_home / "plugins" / "installed_plugins.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    plugins = data.get("plugins", {}) if isinstance(data, dict) else {}
    out = []
    for key, entries in sorted(plugins.items()):
        if isinstance(entries, dict):
            entries = [entries]
        for entry in entries or []:
            install = entry.get("installPath") if isinstance(entry, dict) else None
            if install and (Path(install) / "skills").is_dir():
                out.append((key.split("@")[0], Path(install) / "skills"))
    return out


def default_sources(cwd: Path | None = None, home: Path | None = None) -> list[tuple[str, Path]]:
    home = home or Path.home()
    cwd = cwd or Path.cwd()
    claude_home = Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude"))
    out = [("user", claude_home / "skills"), ("project", cwd / ".claude" / "skills")]
    out += [(f"plugin:{name}", path) for name, path in plugin_skill_dirs(claude_home)]
    return out


def collect(paths: list[str] | None, include_plugins: bool = True) -> list[Skill]:
    if paths:
        sources = [("dir", Path(p)) for p in paths]
    else:
        sources = default_sources()
        if not include_plugins:
            sources = [s for s in sources if not s[0].startswith("plugin:")]
    skills, seen = [], set()
    for source, path in sources:
        for s in find_skills(path, source):
            key = s.path.resolve()
            if key not in seen:
                seen.add(key)
                skills.append(s)
    return skills
