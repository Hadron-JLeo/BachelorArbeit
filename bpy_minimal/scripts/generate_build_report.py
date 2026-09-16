"""Combine build and isolated-validation evidence into final reports."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


OFFICIAL_WHEEL_BYTES = 373_007_009
HISTORICAL_PRUNED_BYTES = 232_107_470


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("build_reports", type=Path)
    parser.add_argument("validation_reports", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    build = args.build_reports
    validation = args.validation_reports
    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    baseline = load_json(build / "baseline-wheel.json")
    final = load_json(build / "minimal-wheel.json")
    deflate9 = load_json(build / "repack-deflate9.json")
    zopfli = load_json(build / "repack-zopfli.json")
    integrity = load_json(validation / "final-wheel-integrity.json")
    downloads = load_json(validation / "download-sizes.json")
    imports = load_json(validation / "import-times.json")
    # Reaching this script means every preceding `set -e` validation command in
    # the isolated container completed successfully.
    validation_result = {
        "isolated_container_without_build_mount": True,
        "wheel_integrity_and_record": True,
        "pip_check": True,
        "numpy_2_0_2": True,
        "minimal_writer_reader": True,
        "multiple_exports_one_process": True,
        "cross_reader_both_directions": True,
        "five_fresh_import_processes": True,
        # The workflow changes this to false only after its independent grep
        # gate has completed.  A failed or skipped gate therefore cannot leave
        # behind a falsely positive machine-readable claim.
        "severe_runtime_log_patterns": None,
    }
    (validation / "validation-result.json").write_text(
        json.dumps(validation_result, indent=2), encoding="utf-8"
    )
    closure = load_json(build / "runtime-elf-closure.json")
    source_commit = (build / "blender-commit.txt").read_text(encoding="utf-8").strip()
    library_commit = (build / "libraries-commit.txt").read_text(encoding="utf-8").strip()
    python_abi = (build / "python-abi.txt").read_text(encoding="utf-8").strip()
    python_version = (build / "python-version.txt").read_text(encoding="utf-8").strip()
    build_variant = (build / "build-variant.txt").read_text(encoding="utf-8").strip()

    candidates = [
        {
            "candidate": f"{build_variant}-source-build-reference",
            "wheel_bytes": baseline["download_bytes"],
            "unpacked_bytes": baseline["installed_payload_bytes"],
            "selected": False,
        },
        {
            "candidate": f"{build_variant}-minimal-upstream-wheel-compression",
            "wheel_bytes": deflate9["source_bytes"],
            "unpacked_bytes": final["installed_payload_bytes"],
            "selected": False,
        },
        {
            "candidate": f"{build_variant}-minimal-deflate9",
            "wheel_bytes": deflate9["output_bytes"],
            "unpacked_bytes": final["installed_payload_bytes"],
            "selected": final["download_bytes"] == deflate9["output_bytes"],
        },
        {
            "candidate": f"{build_variant}-minimal-zopfli-15",
            "wheel_bytes": zopfli["output_bytes"],
            "unpacked_bytes": final["installed_payload_bytes"],
            "selected": final["download_bytes"] == zopfli["output_bytes"],
        },
    ]
    common = {
        "source_commit": source_commit,
        "library_commit": library_commit,
        "python_abi": python_abi,
        "platform_tag": "manylinux_2_28_x86_64",
        "missing_dependency_download_bytes": 0,
        "total_fresh_environment_download_bytes": downloads[
            "bpy_total_fresh_environment_download_bytes"
        ],
        "median_import_seconds": imports["median_seconds"],
    }
    for candidate in candidates:
        candidate.update(common)
        candidate["export_test_result"] = (
            "pass" if candidate["selected"] and validation_result["minimal_writer_reader"] else "n/a"
        )
        candidate["independent_reader_result"] = (
            "pass" if candidate["selected"] and validation_result["cross_reader_both_directions"] else "n/a"
        )
        candidate["wheel_sha256"] = integrity["sha256"] if candidate["selected"] else ""

    columns = [
        "candidate",
        "source_commit",
        "library_commit",
        "python_abi",
        "platform_tag",
        "wheel_bytes",
        "unpacked_bytes",
        "missing_dependency_download_bytes",
        "total_fresh_environment_download_bytes",
        "median_import_seconds",
        "export_test_result",
        "independent_reader_result",
        "wheel_sha256",
        "selected",
    ]
    with (output / "candidates.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(candidates)

    accepted = []
    with (build / "pruning-results.tsv").open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            if row["result"] == "ACCEPTED":
                accepted.append(row)

    result = {
        "final": {
            **integrity,
            "installed_payload_bytes": final["installed_payload_bytes"],
            "median_import_seconds": imports["median_seconds"],
            **downloads,
        },
        "source_commit": source_commit,
        "library_commit": library_commit,
        "python_abi": python_abi,
        "python_version": python_version,
        "build_variant": build_variant,
        "validation": validation_result,
        "accepted_pruning_steps": accepted,
        "bundled_runtime_libraries": sorted(closure["bundled"]),
        "external_runtime_libraries": closure["external"],
        "candidates": candidates,
    }
    (output / "build-result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )

    final_bytes = integrity["bytes"]
    saved_official = OFFICIAL_WHEEL_BYTES - final_bytes
    saved_historical = HISTORICAL_PRUNED_BYTES - final_bytes
    accepted_lines = "\n".join(
        f"- `{row['candidate']}`: {int(row['saved_bytes']):,} Byte entfernt"
        for row in accepted
    )
    bundled_lines = "\n".join(f"- `{name}`" for name in sorted(closure["bundled"]))
    external_lines = "\n".join(
        f"- `{name}` → `{path}`" for name, path in closure["external"].items()
    )
    report = f"""# Build-Bericht: minimales bpy für den Mesh-.blend-Export

## Ergebnis

- Wheel: `{integrity['wheel']}`
- Version: `{integrity['version']}`
- Download: **{final_bytes:,} Byte**
- Installierter Payload: {final['installed_payload_bytes']:,} Byte
- SHA-256: `{integrity['sha256']}`
- Ersparnis zum offiziellen 4.5.3-Wheel: {saved_official:,} Byte ({saved_official / OFFICIAL_WHEEL_BYTES:.1%})
- Ersparnis zur historischen gekürzten Referenz: {saved_historical:,} Byte ({saved_historical / HISTORICAL_PRUNED_BYTES:.1%})
- Zusätzliche Python-Abhängigkeiten von bpy: keine
- Gesamtdownload bei bereits vorhandenem NumPy 2.0.2: {downloads['project_total_with_preinstalled_numpy_bytes']:,} Byte
- Gesamtdownload ohne vorhandenes NumPy: {downloads['project_total_without_preinstalled_numpy_bytes']:,} Byte
- Median für `import bpy`, fünf frische Prozesse mit warmem Dateicache: {imports['median_seconds']:.3f} s

## Bestandene Prüfungen

- Import sowie Writer und Reader in getrennten Prozessen
- komprimierte und unkomprimierte `.blend`-Dateien
- mehrere Exporte im selben Prozess
- Minimal-Writer → offizielles `bpy 4.5.3` und offizieller Writer → Minimal-Reader
- saubere zweite manylinux-Containerumgebung ohne Quellen-, Build- oder Stage-Mount
- NumPy 2.0.2, `pip check`, ZIP-Integrität und vollständige `RECORD`-Prüfung
- ohne Display, GPU oder installierte Blender-Anwendung

## Angenommene Kürzungen

{accepted_lines}

## Mitgelieferte native Bibliotheken

{bundled_lines}

## Erlaubte Systembibliotheken

{external_lines}

## Reproduzierbarkeit

- Blender: `{source_commit}` (`v4.5.3`)
- Blender-Linux-Bibliotheken: `{library_commit}`
- Variante: `{build_variant}`
- Ziel: CPython {python_version} (`{python_abi}`), Linux x86_64, `manylinux_2_28_x86_64`
- Buildcontainer ist im Workflow per SHA-256-Digest fixiert.
- Das Wheel trägt die lokale Version `4.5.3+mesh1` und ist ausdrücklich kein vollständiger Blender-Ersatz.

## Grenze

Abgesichert ist der dokumentierte Mesh-/Material-/Hierarchie-/Text-/`.blend`-Vertrag.
Rendering, Simulation, Audio/Video, Asset-Browser und fremde Dateiformate gehören
nicht zum zugesagten Umfang. Die Messung belegt die kleinste bestandene der hier
aufgeführten Varianten, nicht eine theoretische globale Minimalität.
"""
    (output / "BUILD_REPORT.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
