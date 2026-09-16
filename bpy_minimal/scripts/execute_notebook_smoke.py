"""Execute the release notebook in a real Jupyter kernel."""

from __future__ import annotations

import argparse
from pathlib import Path

import nbformat
from nbclient import NotebookClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=Path)
    parser.add_argument("output_notebook", type=Path)
    parser.add_argument("working_directory", type=Path)
    args = parser.parse_args()

    args.working_directory.mkdir(parents=True, exist_ok=True)
    notebook = nbformat.read(args.notebook, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=900,
        kernel_name="python3",
        resources={"metadata": {"path": str(args.working_directory.resolve())}},
    )
    client.execute()
    nbformat.write(notebook, args.output_notebook)


if __name__ == "__main__":
    main()
