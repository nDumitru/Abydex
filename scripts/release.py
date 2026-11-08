#!/usr/bin/env python3
"""Release helper.

  python scripts/release.py 0.2.0            # bump version + move [Unreleased] notes into [0.2.0]
  python scripts/release.py 0.2.0-beta.1     # pre-release (published as "Pre-release" on GitHub)
  python scripts/release.py --notes 0.2.0    # print the changelog section (used by CI)

It only edits files; it prints the git commands to run, it never pushes by itself.
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "forja3d" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
REPO = "https://github.com/nDumitru/forja3d"
SEMVER = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$")


def current_version() -> str:
    return re.search(r'__version__ = "(.+?)"', INIT.read_text(encoding="utf-8")).group(1)


def notes(version: str) -> str:
    text = CHANGELOG.read_text(encoding="utf-8")
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def bump(new: str) -> None:
    if not SEMVER.match(new):
        sys.exit(f"Versiune invalida: {new} (ex: 0.2.0 sau 0.2.0-beta.1)")
    old = current_version()
    text = CHANGELOG.read_text(encoding="utf-8")
    if f"## [{new}]" in text:
        sys.exit(f"{new} exista deja in CHANGELOG.md")
    unreleased = re.search(r"^## \[Unreleased\]\n(.*?)(?=^## \[)", text, re.S | re.M)
    if not unreleased or not unreleased.group(1).strip():
        sys.exit("Sectiunea [Unreleased] din CHANGELOG.md e goala - noteaza intai ce s-a schimbat.")
    today = datetime.date.today().isoformat()
    text = text.replace(unreleased.group(0), f"## [Unreleased]\n\n## [{new}] - {today}\n{unreleased.group(1)}", 1)
    text = re.sub(r"^\[Unreleased\]: .*$", f"[Unreleased]: {REPO}/compare/v{new}...HEAD\n"
                  f"[{new}]: {REPO}/compare/v{old}...v{new}", text, count=1, flags=re.M)
    CHANGELOG.write_text(text, encoding="utf-8")
    INIT.write_text(INIT.read_text(encoding="utf-8").replace(f'"{old}"', f'"{new}"'), encoding="utf-8")
    print(f"Versiune: {old} -> {new}. Verifica modificarile, apoi:\n")
    print(f'  git commit -am "Release v{new}"')
    print("  git push origin main        # GitHub creeaza automat tag-ul si release-ul")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--notes":
        print(notes(sys.argv[2].lstrip("v")) or "Vezi CHANGELOG.md")
    elif len(sys.argv) == 2:
        bump(sys.argv[1].lstrip("v"))
    else:
        sys.exit(__doc__)
