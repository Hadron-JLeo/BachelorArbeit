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


def contained(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


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

    bundled: dict[str, Path] = {}
    external: dict[str, str] = {}
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

        resolved = Path(resolved_text).resolve()
        if contained(resolved, libraries):
            bundled[soname] = resolved
        else:
            external[soname] = resolved_text

    if not bundled:
        raise SystemExit("ldd found no bundled runtime dependencies")

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
        "external": dict(sorted(external.items())),
        "ldd_before": completed.stdout.splitlines(),
        "ldd_after": verified.stdout.splitlines(),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"kept_runtime_libraries={len(bundled)}")
    print(f"external_runtime_libraries={len(external)}")


if __name__ == "__main__":
    main()
