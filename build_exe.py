import subprocess
import sys

# Build the installer exe using PyInstaller.
#
# @return: None
def main():
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
