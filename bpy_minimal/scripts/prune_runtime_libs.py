"""Keep only shared libraries in the actual ELF dependency closure of bpy.

Blender's install rules copy many precompiled libraries even when the matching
feature is disabled.  They also copy every symlink in a versioned library chain;
the wheel builder dereferences those links and stores the same binary several
times.  This script asks the trusted platform loader for the complete dependency
closure of ``bpy/__init__.so`` and materializes exactly one file under every
required SONAME.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


MAPPED_DEPENDENCY = re.compile(r"^\s*(\S+)\s+=>\s+(\S+)\s+\(0x[0-9a-fA-F]+\)\s*$")
DIRECT_DEPENDENCY = re.compile(r"^\s*(/\S+)\s+\(0x[0-9a-fA-F]+\)\s*$")
DYNAMIC_ENTRY = re.compile(
    r"^\s*0x[0-9a-fA-F]+\s+\((NEEDED|SONAME|RPATH|RUNPATH)\).*\[([^]]*)\]"
)


def contained(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def dynamic_entries(path: Path) -> dict[str, object]:
    completed = subprocess.run(
        ["readelf", "--dynamic", "--wide", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    result: dict[str, object] = {"needed": [], "soname": None, "rpath": [], "runpath": []}
    for line in completed.stdout.splitlines():
        match = DYNAMIC_ENTRY.match(line)
        if not match:
            continue
        kind, value = match.groups()
        if kind == "NEEDED":
            result["needed"].append(value)  # type: ignore[union-attr]
        elif kind == "SONAME":
            result["soname"] = value
        else:
            result[kind.lower()] = value.split(":") if value else []
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    package = (args.stage / "bpy").resolve()
    extension = package / "__init__.so"
    libraries = package / "lib"
    if not extension.is_file() or not libraries.is_dir():
        raise SystemExit(f"Incomplete bpy stage: {args.stage}")

    environment = os.environ.copy()
    environment["LD_LIBRARY_PATH"] = os.pathsep.join(
        filter(None, (str(libraries), environment.get("LD_LIBRARY_PATH", "")))
    )
    completed = subprocess.run(
        ["ldd", str(extension)],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    if "not found" in completed.stdout or "not found" in completed.stderr:
        raise SystemExit(completed.stdout + completed.stderr)

    loader_paths: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        mapped = MAPPED_DEPENDENCY.match(line)
        direct = DIRECT_DEPENDENCY.match(line)
        if mapped:
            soname, resolved_text = mapped.groups()
        elif direct:
            resolved_text = direct.group(1)
            soname = Path(resolved_text).name
        else:
            continue

        loader_paths[soname] = resolved_text

    # Build the graph from ELF DT_NEEDED entries.  `ldd` above and below is an
    # independent check of the loader's actual resolution, not the source of the
    # reachability decision.
    bundled: dict[str, Path] = {}
    external_names: set[str] = set()
    graph: dict[str, dict[str, object]] = {}
    queue = [extension]
    visited: set[Path] = set()
    while queue:
        current = queue.pop()
        resolved_current = current.resolve()
        if resolved_current in visited:
            continue
        visited.add(resolved_current)
        entries = dynamic_entries(resolved_current)
        graph[str(current.relative_to(package))] = entries
        for needed in entries["needed"]:  # type: ignore[union-attr]
            candidate = libraries / needed
            if candidate.exists():
                bundled[needed] = candidate.resolve()
                queue.append(candidate)
            else:
                external_names.add(needed)

    external = {
        name: loader_paths.get(name, "resolved by the system loader")
        for name in sorted(external_names)
    }

    if not bundled:
        raise SystemExit("ldd found no bundled runtime dependencies")

    original_entries = {
        path.name: {
            "bytes_when_wheel_dereferences_link": path.stat().st_size,
            "was_symlink": path.is_symlink(),
        }
        for path in libraries.iterdir()
        if path.is_file() or path.is_symlink()
    }
    removed = {
        name: {**details, "reason": "not reachable from the root ELF DT_NEEDED graph"}
        for name, details in sorted(original_entries.items())
        if name not in bundled
    }

    replacement = package / "lib.required"
    backup = package / "lib.unpruned"
    if replacement.exists() or backup.exists():
        raise SystemExit("Temporary library directory already exists")
    replacement.mkdir()
    for soname, source in sorted(bundled.items()):
        shutil.copy2(source, replacement / soname, follow_symlinks=True)

    libraries.rename(backup)
    replacement.rename(libraries)
    shutil.rmtree(backup)

    # Verify that the compacted directory still resolves the same dependency
    # graph before the higher-level bpy contract tests run.
    verified = subprocess.run(
        ["ldd", str(extension)],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    if "not found" in verified.stdout or "not found" in verified.stderr:
        raise SystemExit(verified.stdout + verified.stderr)

    result = {
        "root_elf": str(extension.relative_to(args.stage.resolve())),
        "bundled": {
            name: {
                "source": str(source),
                "bytes": (libraries / name).stat().st_size,
            }
            for name, source in sorted(bundled.items())
        },
        "removed": removed,
        "external": dict(sorted(external.items())),
        "dynamic_graph": graph,
        "ldd_before": completed.stdout.splitlines(),
        "ldd_after": verified.stdout.splitlines(),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"kept_runtime_libraries={len(bundled)}")
    print(f"external_runtime_libraries={len(external)}")


if __name__ == "__main__":
    main()
