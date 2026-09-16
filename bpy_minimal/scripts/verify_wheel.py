"""Verify ZIP integrity, RECORD, metadata, tags and license of a wheel."""

from __future__ import annotations

import argparse
import base64
import csv
from email.parser import BytesParser
from hashlib import sha256
import io
import json
from pathlib import Path
from zipfile import ZipFile


def digest(data: bytes) -> str:
    encoded = base64.urlsafe_b64encode(sha256(data).digest()).rstrip(b"=")
    return "sha256=" + encoded.decode("ascii")


def file_digest(path: Path) -> str:
    result = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve()

    with ZipFile(wheel) as archive:
        assert archive.testzip() is None
        file_names = {info.filename for info in archive.infolist() if not info.is_dir()}
        record_name = next(name for name in file_names if name.endswith(".dist-info/RECORD"))
        metadata_name = next(name for name in file_names if name.endswith(".dist-info/METADATA"))
        wheel_name = next(name for name in file_names if name.endswith(".dist-info/WHEEL"))
        assert "bpy/licenses/copyright.txt" in file_names
        assert "bpy/licenses/third_party/license.md" in file_names

        rows = list(csv.reader(io.StringIO(archive.read(record_name).decode("utf-8"))))
        assert {row[0] for row in rows} == file_names
        for name, expected_hash, expected_size in rows:
            if name == record_name:
                assert expected_hash == "" and expected_size == ""
                continue
            data = archive.read(name)
            assert expected_hash == digest(data), name
            assert int(expected_size) == len(data), name

        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        wheel_metadata = BytesParser().parsebytes(archive.read(wheel_name))
        requires_dist = metadata.get_all("Requires-Dist", [])
        tags = wheel_metadata.get_all("Tag", [])
        assert metadata["Name"] == "bpy"
        assert metadata["Version"] == "4.5.3+mesh1", metadata["Version"]
        assert metadata["Summary"] == (
            "Unofficial minimal Blender module for tested mesh .blend export only"
        )
        assert not requires_dist, requires_dist
        assert any(tag.endswith("-manylinux_2_28_x86_64") for tag in tags), tags

    result = {
        "wheel": wheel.name,
        "bytes": wheel.stat().st_size,
        "sha256": file_digest(wheel),
        "zip_integrity": "ok",
        "record_entries": len(rows),
        "record_integrity": "ok",
        "name": metadata["Name"],
        "version": metadata["Version"],
        "requires_python": metadata.get("Requires-Python"),
        "requires_dist": requires_dist,
        "tags": tags,
        "license_file": "bpy/licenses/copyright.txt",
        "third_party_license_file": "bpy/licenses/third_party/license.md",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
