"""
deploy/vendor.py — vendor runtime deps for Catalyst's Linux/py3.9 managed runtime.
Run from repo root:  python deploy/vendor.py
"""
import shutil, subprocess, sys
from pathlib import Path

LIB = Path(__file__).resolve().parent / "spear-catalyst" / "lib"
PKGS = ["flask==2.3.3", "waitress==3.0.0"]

def main():
    if LIB.exists():
        shutil.rmtree(LIB)
    LIB.mkdir(parents=True)
    cmd = [sys.executable, "-m", "pip", "install",
           "--target", str(LIB),
           "--platform", "manylinux2014_x86_64",
           "--python-version", "3.9",
           "--implementation", "cp",
           "--only-binary=:all:",
           "--upgrade", *PKGS]
    print(" ".join(cmd))
    subprocess.check_call(cmd)

    # strip build noise
    for p in list(LIB.glob("*.dist-info")) + list(LIB.glob("**/__pycache__")):
        shutil.rmtree(p, ignore_errors=True)

    bad = list(LIB.rglob("*.pyd")) + list(LIB.rglob("*.dll"))
    size = sum(f.stat().st_size for f in LIB.rglob("*") if f.is_file()) / 1e6
    print(f"\nlib/ = {size:.1f} MB")
    if bad:
        print("❌ Windows binaries found — these WILL crash on Catalyst:")
        for b in bad: print("   ", b.relative_to(LIB))
        sys.exit(1)
    print("✅ vendored clean (no .pyd/.dll)")

if __name__ == "__main__":
    main()
