"""Checks for the bundled `clud` skill (skills/autonomous-ai-agents/clud).

Mechanical only: frontmatter, section order, the command surface the skill
promises, and the authoring-standard constraints that are specific to it
(no machine-local paths, no shell-fence continuation hazards).
"""
import re
from pathlib import Path

import hermes_yaml as yaml

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "skills" / "autonomous-ai-agents" / "clud" / "SKILL.md"

REQUIRED_SECTIONS = [
    "## When to Use",
    "## Prerequisites",
    "## How to Run",
    "## Quick Reference",
    "## Procedure",
    "## Pitfalls",
    "## Verification",
]

# The surface the skill promises; if clud drops one of these the doc must change.
PROMISED_COMMANDS = [
    "clud -p",
    "--detach",
    "clud attach",
    "clud list",
    "clud logs",
    "clud kill",
    "clud slay",
    "clud daemon api-info",
]


def _frontmatter_and_body():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---"), "SKILL.md must start with frontmatter"
    match = re.search(r"\n---\s*\n", text[3:])
    assert match, "unclosed frontmatter"
    frontmatter = yaml.safe_load(text[3 : match.start() + 3])
    return frontmatter, text[match.end() + 3 :]


def test_skill_exists():
    assert SKILL.is_file(), f"missing {SKILL.relative_to(REPO)}"


def test_frontmatter_is_complete():
    frontmatter, _ = _frontmatter_and_body()
    for key in ("name", "description", "version", "author", "license", "platforms"):
        assert frontmatter.get(key), f"frontmatter missing {key}"
    assert frontmatter["name"] == "clud"
    assert frontmatter["platforms"] == ["linux", "macos"]
    assert "Hermes Agent" in frontmatter["author"]
    tags = (frontmatter.get("metadata") or {}).get("hermes", {}).get("tags")
    assert tags and "clud" in tags


def test_description_is_one_short_sentence():
    frontmatter, _ = _frontmatter_and_body()
    description = frontmatter["description"]
    assert len(description) <= 60, f"description is {len(description)} chars"
    assert description.endswith("."), "description must end with a period"
    assert description.count(".") == 1, "description must be one sentence"


def test_sections_are_in_modern_order():
    _, body = _frontmatter_and_body()
    positions = [body.find(section) for section in REQUIRED_SECTIONS]
    assert all(p >= 0 for p in positions), f"missing sections: {REQUIRED_SECTIONS}"
    assert positions == sorted(positions), "sections are out of order"


def test_promised_commands_are_documented():
    _, body = _frontmatter_and_body()
    missing = [command for command in PROMISED_COMMANDS if command not in body]
    assert not missing, f"skill no longer documents: {missing}"


def test_no_machine_local_paths():
    _, body = _frontmatter_and_body()
    assert not re.search(r"/home/[a-z0-9_-]+/", body), "use $HOME, not a machine path"


def test_no_hidden_line_continuations():
    _, body = _frontmatter_and_body()
    assert "\\ #" not in body, "a comment after a line continuation breaks the snippet"
