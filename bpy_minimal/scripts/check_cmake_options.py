"""Prüft, ob alle Profiloptionen im festgelegten Blender-Quellstand vorkommen."""

from __future__ import annotations

import json
from pathlib import Path
import re


LAB_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = LAB_ROOT / "source" / "blender"
PROFILE = LAB_ROOT / "config" / "mesh_export.cmake"
REPORT = LAB_ROOT / "reports" / "cmake-option-source-scan.json"


profile_text = PROFILE.read_text(encoding="utf-8")
options = sorted(set(re.findall(r"set\((WITH_[A-Z0-9_]+)", profile_text)))
source_files = [SOURCE_ROOT / "CMakeLists.txt"]
source_files.extend(SOURCE_ROOT.glob("build_files/**/*.cmake"))

occurrences = {option: [] for option in options}
for source_file in source_files:
    try:
        text = source_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for option in options:
        if option in text:
            occurrences[option].append(source_file.relative_to(SOURCE_ROOT).as_posix())

result = {
    "profile": PROFILE.relative_to(LAB_ROOT).as_posix(),
    "source_commit": (LAB_ROOT / "reports" / "blender-commit.txt").read_text().strip(),
    "option_count": len(options),
    "missing_from_source_scan": [option for option, files in occurrences.items() if not files],
    "occurrences": occurrences,
    "limitation": (
        "A text occurrence confirms the option name, not that CMake accepts every combination. "
        "The effective CMakeCache remains authoritative."
    ),
}
REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({key: result[key] for key in ("option_count", "missing_from_source_scan")}, indent=2))
