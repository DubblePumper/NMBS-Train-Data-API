#!/usr/bin/env python3
"""Export API endpoint responses to JSON snapshot files.

Creates a timestamped folder under:
  exports/endpoint_snapshots/<timestamp>/

Each endpoint response is written as its own JSON file, plus a manifest.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request


def utc_now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sanitize_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)


def build_endpoints(include_update: bool = True) -> list[dict[str, Any]]:
    endpoints: list[dict[str, Any]] = [
        {"name": "api_root", "method": "GET", "path": "/api/"},
        {"name": "schema_catalog", "method": "GET", "path": "/api/schema"},
        {"name": "schema_endpoints", "method": "GET", "path": "/api/schema/endpoints"},
        {"name": "schema_realtime", "method": "GET", "path": "/api/schema/realtime_data"},
        {"name": "schema_planning_file", "method": "GET", "path": "/api/schema/planning_file"},
        {"name": "schema_update", "method": "GET", "path": "/api/schema/update"},
        {"name": "health", "method": "GET", "path": "/api/health"},
        {"name": "realtime", "method": "GET", "path": "/api/realtime/data"},
        {"name": "planning_files", "method": "GET", "path": "/api/planningdata/files"},
        {"name": "planning_index", "method": "GET", "path": "/api/planningdata/data"},
        {"name": "planning_stops", "method": "GET", "path": "/api/planningdata/stops?limit=5"},
        {"name": "planning_routes", "method": "GET", "path": "/api/planningdata/routes?limit=5"},
        {"name": "planning_calendar", "method": "GET", "path": "/api/planningdata/calendar?limit=5"},
        {"name": "planning_trips", "method": "GET", "path": "/api/planningdata/trips?limit=5"},
        {"name": "planning_stop_times", "method": "GET", "path": "/api/planningdata/stop_times?limit=5"},
        {"name": "planning_calendar_dates", "method": "GET", "path": "/api/planningdata/calendar_dates?limit=5"},
        {"name": "planning_agency", "method": "GET", "path": "/api/planningdata/agency?limit=5"},
        {"name": "planning_translations", "method": "GET", "path": "/api/planningdata/translations?limit=5"},
        {"name": "cache_index", "method": "GET", "path": "/api/cache"},
        {"name": "cache_realtime", "method": "GET", "path": "/api/cache/realtime"},
        {"name": "deprecated_data", "method": "GET", "path": "/api/data"},
        {"name": "security_audit", "method": "GET", "path": "/api/security/audit"},
        {"name": "trajectories", "method": "GET", "path": "/api/trajectories?limit=5"},
    ]

    if include_update:
        endpoints.append(
            {
                "name": "update",
                "method": "POST",
                "path": "/api/update",
                "body": {"force": True, "update_type": "realtime"},
            }
        )

    return endpoints


def call_endpoint(base_url: str, spec: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{spec['path']}"
    method = spec.get("method", "GET").upper()

    headers = {"Accept": "application/json"}
    data_bytes = None

    if "body" in spec:
        headers["Content-Type"] = "application/json"
        data_bytes = json.dumps(spec["body"]).encode("utf-8")

    req = request.Request(url=url, method=method, headers=headers, data=data_bytes)

    status = -1
    response_headers: dict[str, str] = {}
    raw_text = ""

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            response_headers = dict(resp.headers.items())
            raw_text = resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as ex:
        status = ex.code
        response_headers = dict(ex.headers.items()) if ex.headers else {}
        raw_text = ex.read().decode("utf-8", errors="replace")
    except Exception as ex:  # noqa: BLE001
        return {
            "name": spec["name"],
            "method": method,
            "url": url,
            "ok": False,
            "status": status,
            "fetched_at": utc_now_iso(),
            "error": str(ex),
            "is_json": False,
            "body": None,
        }

    parsed_json = None
    is_json = False
    try:
        parsed_json = json.loads(raw_text)
        is_json = True
    except Exception:  # noqa: BLE001
        is_json = False

    return {
        "name": spec["name"],
        "method": method,
        "url": url,
        "ok": 200 <= status < 300,
        "status": status,
        "fetched_at": utc_now_iso(),
        "request_body": spec.get("body"),
        "response_headers": response_headers,
        "is_json": is_json,
        "body": parsed_json if is_json else raw_text,
    }


def export_snapshots(base_url: str, output_root: Path, include_update: bool = True) -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    export_dir = output_root / "endpoint_snapshots" / timestamp
    export_dir.mkdir(parents=True, exist_ok=True)

    endpoints = build_endpoints(include_update=include_update)
    manifest = {
        "exported_at": utc_now_iso(),
        "base_url": base_url,
        "endpoint_count": len(endpoints),
        "files": [],
    }

    for spec in endpoints:
        result = call_endpoint(base_url, spec)
        file_name = f"{sanitize_name(spec['name'])}.json"
        file_path = export_dir / file_name

        with file_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        manifest["files"].append(
            {
                "name": spec["name"],
                "path": file_name,
                "status": result.get("status"),
                "ok": result.get("ok"),
                "is_json": result.get("is_json"),
            }
        )

    with (export_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return export_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Export API endpoint responses to JSON files")
    parser.add_argument("--base-url", default="http://localhost:25580", help="API base URL")
    parser.add_argument(
        "--output-root",
        default=os.getenv("SNAPSHOT_ROOT", "exports"),
        help="Root output folder (timestamped subfolder is created automatically)",
    )
    parser.add_argument(
        "--skip-update",
        action="store_true",
        help="Skip POST /api/update during export",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root)
    export_dir = export_snapshots(
        base_url=args.base_url,
        output_root=output_root,
        include_update=not args.skip_update,
    )

    print(str(export_dir))


if __name__ == "__main__":
    main()
