"""Test runner script with coverage reporting.

This module provides a Poetry console script for running tests.
Script is registered in pyproject.toml under [tool.poetry.scripts]
and invoked via `poetry run test`.

References:
    - Poetry scripts: https://python-poetry.org/docs/pyproject/#scripts
    - pytest: https://docs.pytest.org/
    - coverage: https://coverage.readthedocs.io/
"""

import subprocess
import sys


def main() -> int:
    """Run pytest with coverage reports."""
    print("Running tests with coverage...\n")

    result = subprocess.run(
        [
            "pytest",
            "tests/",
            "--cov=src/pisolar",
            "--cov-report=html",
            "--cov-report=term",
            "-v",
        ]
    )

    if result.returncode == 0:
        print("\n✓ All tests passed!")
        print("Coverage report: reports/htmlcov/index.html")
    else:
        print("\n✗ Some tests failed")

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
