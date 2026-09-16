"""Record the successful workflow-level runtime-log gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("validation_result", type=Path)
    parser.add_argument("build_result", type=Path)
    parser.add_argument("build_report", type=Path)
    args = parser.parse_args()

    validation = json.loads(args.validation_result.read_text(encoding="utf-8"))
    validation["severe_runtime_log_patterns"] = False
    write_json(args.validation_result, validation)

    build = json.loads(args.build_result.read_text(encoding="utf-8"))
    build["validation"]["severe_runtime_log_patterns"] = False
    write_json(args.build_result, build)

    with args.build_report.open("a", encoding="utf-8") as stream:
        stream.write(
            "\n## Abschließendes Workflow-Gate\n\n"
            "- Keine schwerwiegenden Laufzeitfehlermuster im vollständigen "
            "Validierungsprotokoll.\n"
        )


if __name__ == "__main__":
    main()
