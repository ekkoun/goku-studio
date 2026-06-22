"""Git-backed skills repo — the writer side of Plan A.

Studio is the **sole committer** to the canonical skills Git repo. This module
keeps a writable local clone; reads come from the clone, and create/edit/delete
operations write the file, validate its frontmatter, commit, and push. Core then
picks up the change via its webhook→pull sync.

When SKILLS_GIT_URL is unset everything is a no-op / falls back to the local
skills directory, so dev and legacy single-container deployments are unchanged.

Env vars:
  SKILLS_GIT_URL           Git URL incl. auth token
  SKILLS_GIT_BRANCH        Branch to commit to (default: main)
  SKILLS_REPO_DIR          Writable clone path (default: $AGENT_WORKSPACE/skills-repo)
  SKILLS_GIT_AUTHOR_NAME   Commit author name  (default: Goku Studio)
  SKILLS_GIT_AUTHOR_EMAIL  Commit author email (default: studio@goku.local)
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)
_LOCK = threading.RLock()


def is_enabled() -> bool:
    return bool(os.environ.get("SKILLS_GIT_URL"))


def _branch() -> str:
    return os.environ.get("SKILLS_GIT_BRANCH", "main")


def repo_dir() -> Path:
    override = os.environ.get("SKILLS_REPO_DIR")
    if override:
        return Path(override)
    workspace = os.environ.get("AGENT_WORKSPACE", "/tmp/agent_workspace")
    return Path(workspace) / "skills-repo"


def _git(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, timeout=timeout)


def ensure_clone(pull: bool = False) -> Path:
    """Ensure a writable clone exists. With pull=True, also fast-forward to the
    remote branch tip — done before writes (to avoid push conflicts), NOT on every
    read (that would be a network round-trip per skill lookup)."""
    d = repo_dir()
    url = os.environ["SKILLS_GIT_URL"]
    br = _branch()
    with _LOCK:
        fresh = not (d / ".git").exists()
        if fresh:
            d.parent.mkdir(parents=True, exist_ok=True)
            _git(["clone", "--branch", br, url, str(d)], timeout=180)
            _git(["-C", str(d), "config", "user.name", os.environ.get("SKILLS_GIT_AUTHOR_NAME", "Goku Studio")])
            _git(["-C", str(d), "config", "user.email", os.environ.get("SKILLS_GIT_AUTHOR_EMAIL", "studio@goku.local")])
        elif pull:
            _git(["-C", str(d), "fetch", "origin", br])
            _git(["-C", str(d), "checkout", "-B", br, f"origin/{br}"])
    return d


def clone_path_or_none() -> Path | None:
    """The clone path for reads, or None when git is disabled/unavailable."""
    if not is_enabled():
        return None
    try:
        return ensure_clone()
    except Exception as e:  # noqa: BLE001
        logger.error("skills repo clone failed: %s", e)
        return None


def validate_frontmatter(content: str) -> tuple[bool, str]:
    """Validate a SKILL.md's YAML frontmatter. No frontmatter block is allowed."""
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return True, ""
    try:
        yaml.safe_load(m.group(1))
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, str(e).splitlines()[0]


def write_skill(skill_id: str, files: dict[str, str], message: str) -> dict:
    """Create/overwrite a skill (files = {relative_path: content}); validate the
    SKILL.md frontmatter, commit, and push. Raises on validation/git failure."""
    if not is_enabled():
        raise RuntimeError("Skills git repo not configured (SKILLS_GIT_URL).")
    md = files.get("SKILL.md")
    if md is not None:
        ok, err = validate_frontmatter(md)
        if not ok:
            raise ValueError(f"Invalid SKILL.md frontmatter: {err}")
    with _LOCK:
        d = ensure_clone(pull=True)
        sdir = d / skill_id
        sdir.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            p = sdir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return _commit_push(d, message, skill_id)


def remove_skill(skill_id: str, message: str) -> dict:
    if not is_enabled():
        raise RuntimeError("Skills git repo not configured (SKILLS_GIT_URL).")
    with _LOCK:
        d = ensure_clone(pull=True)
        sdir = d / skill_id
        if sdir.exists():
            import shutil
            shutil.rmtree(sdir)
        return _commit_push(d, message, skill_id)


def _commit_push(d: Path, message: str, skill_id: str) -> dict:
    _git(["-C", str(d), "add", "-A"])
    if not _git(["-C", str(d), "status", "--porcelain"]).stdout.strip():
        return {"ok": True, "skill_id": skill_id, "changed": False}
    _git(["-C", str(d), "commit", "-m", message])
    _git(["-C", str(d), "push", "origin", _branch()], timeout=120)
    head = _git(["-C", str(d), "rev-parse", "--short", "HEAD"]).stdout.strip()
    logger.info("Skill '%s' committed+pushed: %s", skill_id, head)
    return {"ok": True, "skill_id": skill_id, "changed": True, "commit": head}


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9一-鿿]+", "-", (name or "").lower()).strip("-")
    return s or "skill"


def build_skill_md(auto_skill) -> str:
    """Render an approved AutoSkill (DB candidate) into canonical SKILL.md text."""
    fm = {
        "name": auto_skill.name,
        "description": auto_skill.description,
        "trigger_keywords": auto_skill.trigger_keywords or [],
        "tools_required": auto_skill.tools_required or [],
        "category": "auto",
        "status": "approved",
    }
    front = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()
    body = auto_skill.workflow_md or ""
    return f"---\n{front}\n---\n\n{body}\n"


def auto_skill_id(name: str) -> str:
    """Canonical repo directory id for a promoted auto-skill."""
    return f"auto-{_slug(name)}"
