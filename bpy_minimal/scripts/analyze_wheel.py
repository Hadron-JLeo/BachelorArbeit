"""Schreibt reproduzierbare Größen- und Inhaltsdaten für ein bpy-Wheel."""

from __future__ import annotations

import argparse
from collections import defaultdict
from email.parser import BytesParser
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    wheel = args.wheel.resolve()
    groups: dict[str, dict[str, int]] = defaultdict(
        lambda: {"files": 0, "compressed_bytes": 0, "uncompressed_bytes": 0}
    )
    with ZipFile(wheel) as archive:
        metadata_path = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        metadata = BytesParser().parsebytes(archive.read(metadata_path))
        members = []
        for info in archive.infolist():
            if info.is_dir():
                continue
            top_level = info.filename.split("/", 1)[0]
            group = groups[top_level]
            group["files"] += 1
            group["compressed_bytes"] += info.compress_size
            group["uncompressed_bytes"] += info.file_size
            members.append({
                "path": info.filename,
                "compressed_bytes": info.compress_size,
                "uncompressed_bytes": info.file_size,
            })

    compressed_bytes = wheel.stat().st_size
    uncompressed_bytes = sum(item["uncompressed_bytes"] for item in members)
    result = {
        "wheel": wheel.name,
        "sha256": file_sha256(wheel),
        "download_bytes": compressed_bytes,
        "installed_payload_bytes": uncompressed_bytes,
        "compression_ratio": uncompressed_bytes / compressed_bytes,
        "file_count": len(members),
        "requires_python": metadata.get("Requires-Python"),
        "requires_dist": metadata.get_all("Requires-Dist", []),
        "top_level": dict(sorted(groups.items())),
        "largest_uncompressed": sorted(
            members, key=lambda item: item["uncompressed_bytes"], reverse=True
        )[:50],
        "largest_compressed": sorted(
            members, key=lambda item: item["compressed_bytes"], reverse=True
        )[:50],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        f"wheel={wheel.name}\n"
        f"download_bytes={compressed_bytes}\n"
        f"installed_payload_bytes={uncompressed_bytes}\n"
        f"sha256={result['sha256']}"
    )


if __name__ == "__main__":
    main()
