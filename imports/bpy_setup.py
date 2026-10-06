"""Installation der veröffentlichten Minimal-bpy-Wheels mit SHA-256-Prüfung."""

from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
import sysconfig
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.request import urlretrieve


BPY_VERSION = "4.5.3+mesh1"
RELEASE_URL = (
    "https://github.com/Hadron-JLeo/BachelorArbeit/releases/download/"
    "bpy-mesh-4.5.3.1"
)
WHEELS = {
    "3.11": (
        "bpy-4.5.3+mesh1-cp311-cp311-manylinux_2_28_x86_64.whl",
        "651c74dce5c00b1a822c4ff0d78d6d0cf3904079a78308e171acf28e53629409",
    ),
    "3.12": (
        "bpy-4.5.3+mesh1-cp312-cp312-manylinux_2_28_x86_64.whl",
        "1f26833ce95fd2c60f42d9f44b34a97326a3a6246d0b3d177d59fb83e99e2ff5",
    ),
}


def _select_wheel() -> tuple[str, str]:
    """Prüft die Laufzeitumgebung und wählt das dazu passende Wheel."""
    python_key = f"{sys.version_info.major}.{sys.version_info.minor}"
    if python_key not in WHEELS:
        raise RuntimeError(
            f"Kein Minimal-bpy-Wheel für Python {python_key}. "
            "Bitte einen Kernel mit Python 3.11 oder 3.12 verwenden."
        )
    if not sys.platform.startswith("linux") or platform.machine() not in {
        "x86_64", "AMD64"
    }:
        raise RuntimeError("Minimal-bpy benötigt Linux x86_64.")
    libc_name, libc_version = platform.libc_ver()
    if libc_name != "glibc" or tuple(map(int, libc_version.split(".")[:2])) < (2, 28):
        raise RuntimeError("Minimal-bpy benötigt glibc 2.28 oder neuer.")
    soabi = sysconfig.get_config_var("SOABI") or ""
    if not soabi.startswith(f"cpython-{sys.version_info.major}{sys.version_info.minor}-"):
        raise RuntimeError("Minimal-bpy benötigt den passenden CPython-Interpreter.")
    return WHEELS[python_key]


def install_minimal_bpy() -> None:
    """Installiert Minimal-bpy einmalig im aktiven Notebook-Interpreter."""
    wheel_name, expected_hash = _select_wheel()
    try:
        installed_version = version("bpy")
    except PackageNotFoundError:
        installed_version = None

    if installed_version == BPY_VERSION:
        print(f"Minimal-bpy {BPY_VERSION} ist bereits installiert.")
        return
    if "bpy" in sys.modules:
        raise RuntimeError(
            "Eine andere bpy-Version ist bereits geladen. "
            "Bitte den Kernel neu starten und zuerst die Installationszelle ausführen."
        )

    with tempfile.TemporaryDirectory(prefix="hypercube-bpy-") as directory:
        wheel_path = Path(directory) / wheel_name
        urlretrieve(f"{RELEASE_URL}/{wheel_name}", wheel_path)
        actual_hash = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise RuntimeError("SHA-256-Prüfung fehlgeschlagen; bpy wurde nicht installiert.")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--no-cache-dir",
            "--no-deps", "--force-reinstall", str(wheel_path),
        ])
    if version("bpy") != BPY_VERSION:
        raise RuntimeError("Die erwartete Minimal-bpy-Version wurde nicht installiert.")
    print(f"Minimal-bpy {BPY_VERSION} ist installiert.")
