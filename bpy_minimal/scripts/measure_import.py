"""Measure direct bpy import time in independent interpreter processes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import subprocess


CODE = """\
import json
import time
started = time.perf_counter()
import bpy
elapsed = time.perf_counter() - started
print(json.dumps({"seconds": elapsed, "bpy_file": bpy.__file__, "version": bpy.app.version_string}))
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("python", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    assert args.repetitions >= 5

    runs = []
    for _ in range(args.repetitions):
        completed = subprocess.run(
            [str(args.python), "-c", CODE],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout.splitlines()[-1])
        payload["stderr"] = completed.stderr
        runs.append(payload)

    result = {
        "cache_state": "warm (after functional validation)",
        "repetitions": args.repetitions,
        "median_seconds": statistics.median(run["seconds"] for run in runs),
        "runs": runs,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
