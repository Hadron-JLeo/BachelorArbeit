"""Repack a wheel with deterministic DEFLATE-9 or Zopfli-DEFLATE."""

from __future__ import annotations

import argparse
import binascii
from hashlib import sha256
import json
from pathlib import Path
import struct
from zipfile import ZipFile
import zlib


LOCAL_HEADER = struct.Struct("<IHHHHHIIIHH")
CENTRAL_HEADER = struct.Struct("<IHHHHHHIIIHHHHHII")
END_HEADER = struct.Struct("<IHHHHIIH")


def dos_datetime(parts: tuple[int, int, int, int, int, int]) -> tuple[int, int]:
    year, month, day, hour, minute, second = parts
    year = min(max(year, 1980), 2107)
    return (
        (hour << 11) | (minute << 5) | (second // 2),
        ((year - 1980) << 9) | (month << 5) | day,
    )


def deflate9(data: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    return compressor.compress(data) + compressor.flush()


def zopfli_deflate(data: bytes, iterations: int) -> bytes:
    from zopfli import zlib as zopfli_zlib

    wrapped = zopfli_zlib.compress(data, numiterations=iterations)
    if len(wrapped) < 6:
        raise ValueError("Invalid Zopfli zlib stream")
    raw = wrapped[2:-4]
    if zlib.decompress(raw, wbits=-15) != data:
        raise ValueError("Zopfli raw-DEFLATE verification failed")
    return raw


def write_zip(source: Path, output: Path, mode: str, iterations: int) -> dict[str, int]:
    entries: list[dict[str, object]] = []
    with ZipFile(source) as archive, output.open("wb") as target:
        for info in archive.infolist():
            name = info.filename.encode("utf-8")
            data = archive.read(info.filename)
            if info.is_dir():
                method = 0
                compressed = data
            else:
                method = 8
                compressed = (
                    deflate9(data)
                    if mode == "deflate9"
                    else zopfli_deflate(data, iterations)
                )
            crc = binascii.crc32(data) & 0xFFFFFFFF
            mod_time, mod_date = dos_datetime(info.date_time)
            flags = 0x800
            offset = target.tell()
            target.write(
                LOCAL_HEADER.pack(
                    0x04034B50,
                    20,
                    flags,
                    method,
                    mod_time,
                    mod_date,
                    crc,
                    len(compressed),
                    len(data),
                    len(name),
                    0,
                )
            )
            target.write(name)
            target.write(compressed)
            entries.append(
                {
                    "name": name,
                    "method": method,
                    "time": mod_time,
                    "date": mod_date,
                    "crc": crc,
                    "compressed": len(compressed),
                    "uncompressed": len(data),
                    "create_version": (info.create_system << 8) | max(info.create_version, 20),
                    "internal_attr": info.internal_attr,
                    "external_attr": info.external_attr,
                    "offset": offset,
                }
            )

        central_offset = target.tell()
        for entry in entries:
            name = entry["name"]
            target.write(
                CENTRAL_HEADER.pack(
                    0x02014B50,
                    entry["create_version"],
                    20,
                    0x800,
                    entry["method"],
                    entry["time"],
                    entry["date"],
                    entry["crc"],
                    entry["compressed"],
                    entry["uncompressed"],
                    len(name),
                    0,
                    0,
                    0,
                    entry["internal_attr"],
                    entry["external_attr"],
                    entry["offset"],
                )
            )
            target.write(name)
        central_size = target.tell() - central_offset
        if len(entries) > 0xFFFF or target.tell() > 0xFFFFFFFF:
            raise ValueError("ZIP64 would be required")
        target.write(
            END_HEADER.pack(
                0x06054B50,
                0,
                0,
                len(entries),
                len(entries),
                central_size,
                central_offset,
                0,
            )
        )
    return {
        "files": len(entries),
        "compressed_payload_bytes": sum(int(entry["compressed"]) for entry in entries),
    }


def content_hashes(path: Path) -> dict[str, str]:
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        return {
            info.filename: sha256(archive.read(info.filename)).hexdigest()
            for info in archive.infolist()
            if not info.is_dir()
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--mode", choices=("deflate9", "zopfli"), required=True)
    parser.add_argument("--iterations", type=int, default=15)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if source == output or output.suffix != ".whl":
        raise SystemExit("Input and output must be distinct wheel paths")
    output.parent.mkdir(parents=True, exist_ok=True)

    details = write_zip(source, output, args.mode, args.iterations)
    assert content_hashes(source) == content_hashes(output)
    result = {
        "mode": args.mode,
        "zopfli_iterations": args.iterations if args.mode == "zopfli" else None,
        "source_bytes": source.stat().st_size,
        "output_bytes": output.stat().st_size,
        "saved_bytes": source.stat().st_size - output.stat().st_size,
        "uncompressed_contents_byte_identical": True,
        **details,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
