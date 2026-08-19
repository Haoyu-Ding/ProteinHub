#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from proteinhub.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check optional ProteinHub external tool configuration.",
    )
    parser.add_argument(
        "--env-file",
        default="/etc/proteinhub.env",
        help="Environment file to load before checking paths.",
    )
    parser.add_argument(
        "--require-akta",
        action="store_true",
        help="Exit non-zero if AKTA rendering is not fully configured.",
    )
    parser.add_argument(
        "--require-domesticator",
        action="store_true",
        help="Exit non-zero if legacy domesticator optimization is not fully configured.",
    )
    args = parser.parse_args()

    load_env_file(Path(args.env_file))
    settings = get_settings()

    failures: list[str] = []
    print("ProteinHub external tool check")
    print("")
    check_tool(
        "AKTA renderer",
        {
            "python": settings.akta_hap_python,
            "script": settings.akta_hap_script,
        },
        required=args.require_akta,
        failures=failures,
    )
    print("")
    check_tool(
        "Legacy domesticator",
        {
            "python": settings.legacy_domesticator_python,
            "script": settings.legacy_domesticator_script,
            "database": settings.legacy_domesticator_database,
        },
        required=args.require_domesticator,
        failures=failures,
    )

    if failures:
        print("")
        print("Failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        parsed = shlex.split(value, comments=False, posix=True)
        os.environ[key] = parsed[0] if parsed else ""


def check_tool(
    name: str,
    paths: dict[str, Path | None],
    *,
    required: bool,
    failures: list[str],
) -> None:
    configured = all(path is not None for path in paths.values())
    status = "configured" if configured else "optional and not fully configured"
    print(f"{name}: {status}")

    for label, path in paths.items():
        if path is None:
            print(f"  {label}: missing")
            if required:
                failures.append(f"{name} {label} is not configured")
            continue
        ok = path.is_dir() if label == "database" else path.is_file()
        if label == "python":
            ok = ok and os.access(path, os.X_OK)
        print(f"  {label}: {path} {'ok' if ok else 'missing'}")
        if required and not ok:
            failures.append(f"{name} {label} does not exist or is not usable: {path}")


if __name__ == "__main__":
    sys.exit(main())
