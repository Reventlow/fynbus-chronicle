#!/usr/bin/env python3
"""
Calculate the next version number based on version.txt.

Increments the patch version by 1 (e.g., 0.1.0 -> 0.1.1).
"""

from pathlib import Path


def main():
    version_file = Path(__file__).parent.parent / "version.txt"

    if not version_file.exists():
        # Start with initial version if file doesn't exist
        print("0.1.0")
        return

    current_version = version_file.read_text().strip()

    try:
        parts = current_version.split(".")
        if len(parts) == 3:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            # Increment patch version
            new_version = f"{major}.{minor}.{patch + 1}"
        else:
            # Fallback for non-semver versions
            new_version = f"{float(current_version) + 0.01:.2f}"
    except ValueError:
        # If parsing fails, start fresh
        new_version = "0.1.0"

    print(new_version)


if __name__ == "__main__":
    main()
