"""
PyInstaller build script for the Modded Among Us Installer.

Usage:
    python build_exe.py
"""

import subprocess
import sys


def main():
    """
    Build the installer exe using PyInstaller.

    @return: None
    """
    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "ModdedAmongUsInstaller",
        "--console",
        "--clean",
        "install_modpack.py",
    ]
    result = subprocess.run(args)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
