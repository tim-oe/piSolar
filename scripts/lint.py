"""Lint script that runs black, isort, and flake8 on the src tree."""

import subprocess
import sys


def main() -> int:
    """Run all linting tools on src and tests directories."""
    targets = ["src", "tests"]
    failed = False

    # Run isort (import sorting)
    print("Running isort...")
    result = subprocess.run(["isort", "--check-only", "--diff", *targets])
    if result.returncode != 0:
        failed = True

    # Run black (code formatting)
    print("\nRunning black...")
    result = subprocess.run(["black", "--check", "--diff", *targets])
    if result.returncode != 0:
        failed = True

    # Run flake8 (style checking)
    print("\nRunning flake8...")
    result = subprocess.run(["flake8", *targets])
    if result.returncode != 0:
        failed = True

    if failed:
        print("\nLinting failed. Run 'poetry run format' to auto-fix issues.")
        return 1

    print("\nAll linting checks passed!")
    return 0


def format_code() -> int:
    """Auto-format code with isort and black."""
    targets = ["src", "tests"]

    print("Running isort...")
    subprocess.run(["isort", *targets])

    print("\nRunning black...")
    subprocess.run(["black", *targets])

    print("\nFormatting complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
