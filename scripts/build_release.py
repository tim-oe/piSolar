#!/usr/bin/env python3
"""
piSolar Release Builder
Creates a deployment package ready for runtime installation
Reads version from pyproject.toml
"""
import os
import sys
import shutil
import subprocess
import tomllib
from pathlib import Path


def get_version() -> str:
    """Get version from pyproject.toml"""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("Error: pyproject.toml not found", file=sys.stderr)
        sys.exit(1)
    
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    
    version = pyproject.get("project", {}).get("version")
    if not version:
        print("Error: version not found in pyproject.toml [project] section", file=sys.stderr)
        sys.exit(1)
    
    return version


def build_release(version: str = None):
    """Build release package"""
    
    if version is None:
        version = get_version()
    
    archive_name = f"pisolar-{version}.tar.gz"
    build_dir = Path("build/release")
    release_dir = build_dir / "pisolar"
    
    print("=== Building piSolar Release Package ===")
    print(f"Version: {version} (from pyproject.toml)")
    print(f"Archive: {archive_name}")
    print()
    
    # Clean previous builds
    print("[1/4] Cleaning previous builds...")
    if build_dir.parent.exists():
        shutil.rmtree(build_dir.parent)
    release_dir.mkdir(parents=True)
    
    # Copy runtime files
    print("[2/4] Copying runtime files...")
    
    print("  - Source code (src/pisolar/)")
    shutil.copytree("src/pisolar", release_dir / "pisolar")
    
    print("  - Configuration files (config/)")
    shutil.copytree("config", release_dir / "config")
    
    print("  - Systemd service (systemd/)")
    shutil.copytree("systemd", release_dir / "systemd")
    
    print("  - Requirements (requirements.txt)")
    shutil.copy("requirements.txt", release_dir / "requirements.txt")
    
    print("  - Installation script (install.sh)")
    shutil.copy("install.sh", release_dir / "install.sh")
    os.chmod(release_dir / "install.sh", 0o755)
    
    # Remove Python cache
    print("[3/4] Cleaning Python cache files...")
    for pattern in ["__pycache__", "*.pyc", "*.pyo"]:
        for path in release_dir.rglob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    
    # Create archive
    print("[4/4] Creating release archive...")
    subprocess.run(
        ["tar", "-czf", archive_name, "pisolar"],
        cwd=build_dir,
        check=True
    )
    
    # Calculate size
    archive_path = build_dir / archive_name
    size_bytes = archive_path.stat().st_size
    size_kb = size_bytes / 1024
    size = f"{size_kb:.0f}K" if size_kb < 1024 else f"{size_kb/1024:.1f}M"
    
    print()
    print("=== Release Package Created ===")
    print(f"Package: build/release/{archive_name}")
    print(f"Size: {size}")
    print()
    print("Archive structure:")
    print("  pisolar/")
    print("  ├── pisolar/          (Python application)")
    print("  ├── config/           (Configuration files)")
    print("  ├── systemd/          (Service definition)")
    print("  ├── requirements.txt  (Dependencies)")
    print("  └── install.sh        (Installation script)")
    print()
    print("To deploy:")
    print(f"  1. Copy {archive_name} to target system")
    print(f"  2. tar -xzf {archive_name}")
    print("  3. cd pisolar")
    print("  4. sudo ./install.sh")
    print()
    print("GitHub Release:")
    print(f"  gh release create v{version} build/release/{archive_name} --title \"Release v{version}\" --notes \"Release v{version}\"")
    print()
    print("Build complete!")
    
    return 0


def main():
    """Main entry point"""
    version = get_version()
    return build_release(version)


if __name__ == "__main__":
    sys.exit(main())
