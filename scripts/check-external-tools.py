#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from proteinhub.config import get_settings
from proteinhub.domain.errors import DomainError
from proteinhub.infrastructure.translation.legacy_domesticator import (
    optimize_with_legacy_domesticator,
)


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
    parser.add_argument(
        "--smoke-domesticator",
        action="store_true",
        help="Run a short legacy domesticator optimization smoke test.",
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
    if args.smoke_domesticator:
        print("")
        smoke_check_domesticator(settings, failures)

    if failures:
        print("")
        print("Failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


def smoke_check_domesticator(settings, failures: list[str]) -> None:
    print("Legacy domesticator smoke test:")
    started_at = time.monotonic()
    try:
        result = optimize_with_legacy_domesticator(
            {"A01_smoke": "MGK"},
            settings=settings,
        )
    except DomainError as error:
        print(f"  failed: {error.message}")
        failures.append(f"Legacy domesticator smoke test failed: {error.message}")
        return
    elapsed = time.monotonic() - started_at
    dna = result.get("A01_smoke", "")
    print(f"  ok: optimized 1 record in {elapsed:.1f}s ({len(dna)} bp)")


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
