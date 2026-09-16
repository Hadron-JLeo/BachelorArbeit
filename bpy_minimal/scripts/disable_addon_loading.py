"""Deaktiviert Blenders Extension-Lader nur in einem Kandidaten-Stage."""

from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path


REPLACEMENT = '''def load_scripts_extensions(*, reload_scripts=False):
    """Add-ons and app templates are unavailable in this mesh-export build."""
    del reload_scripts
'''


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("module", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    original_bytes = args.module.read_bytes()
    original = original_bytes.decode("utf-8")
    tree = ast.parse(original, filename=str(args.module))
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "load_scripts_extensions"
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected one load_scripts_extensions function, found {len(matches)}")
    node = matches[0]
    if node.end_lineno is None:
        raise SystemExit("Python AST has no end position for load_scripts_extensions")

    lines = original.splitlines(keepends=True)
    replacement = REPLACEMENT.splitlines(keepends=True)
    modified = "".join(lines[: node.lineno - 1] + replacement + lines[node.end_lineno :])
    compile(modified, str(args.module), "exec")
    if "_initialize_once()" in modified:
        raise SystemExit("Extension initialization call remained after patching")

    modified_bytes = modified.encode("utf-8")
    args.module.write_bytes(modified_bytes)
    result = {
        "module": str(args.module),
        "function": "load_scripts_extensions",
        "behavior": "disabled for the documented minimal mesh-export scope",
        "before_sha256": digest(original_bytes),
        "after_sha256": digest(modified_bytes),
        "before_bytes": len(original_bytes),
        "after_bytes": len(modified_bytes),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
