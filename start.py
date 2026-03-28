#!/usr/bin/env python3
"""
Single-file launcher for NMBS Train Data API.

Usage:
  python start.py

By default this starts:
  - web API
  - background data service
  - host/port from .env
  - tests disabled at startup

Any provided CLI args are forwarded to nmbs_api.cli.web_runner.
"""

import os
import sys

from dotenv import load_dotenv


def _is_truthy(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    project_root = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(project_root, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    load_dotenv()

    from nmbs_api.cli.web_runner import main as web_main

    forwarded = list(sys.argv[1:])

    # Friendly alias: --interval -> --data-interval
    normalized = []
    i = 0
    while i < len(forwarded):
        if forwarded[i] == "--interval":
            normalized.append("--data-interval")
        else:
            normalized.append(forwarded[i])
        i += 1
    forwarded = normalized

    # Custom convenience switch: --web-only disables background data service startup
    web_only = "--web-only" in forwarded
    forwarded = [arg for arg in forwarded if arg != "--web-only"]

    host = os.getenv("API_HOST", "0.0.0.0")
    port = os.getenv("API_PORT", "25580")

    run_tests_on_start = _is_truthy(os.getenv("RUN_TESTS_ON_START", "false"), default=False)

    # Defaults when not explicitly provided
    if "--host" not in forwarded:
        forwarded.extend(["--host", host])
    if "--port" not in forwarded:
        forwarded.extend(["--port", str(port)])
    if not web_only and "--with-data-service" not in forwarded:
        forwarded.append("--with-data-service")
    if not run_tests_on_start and "--no-tests" not in forwarded:
        forwarded.append("--no-tests")

    sys.argv = [sys.argv[0], *forwarded]
    web_main()


if __name__ == "__main__":
    main()
