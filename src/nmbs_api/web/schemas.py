"""Versioned API schema catalog for NMBS Train Data API."""

from copy import deepcopy

from .config import API_NAME, API_VERSION

SCHEMA_SPEC_VERSION = "1.0.0"

BASE_ENVELOPE_SCHEMA = {
    "type": "object",
    "required": ["ok", "metadata"],
    "properties": {
        "ok": {"type": "boolean"},
        "metadata": {
            "type": "object",
            "required": ["api_name", "version", "endpoint", "data_type", "generated_at"],
            "properties": {
                "api_name": {"type": "string"},
                "version": {"type": "string"},
                "endpoint": {"type": "string"},
                "data_type": {"type": ["string", "null"]},
                "generated_at": {"type": "string"},
                "record_count": {"type": "integer"},
                "total_records": {"type": "integer"},
                "page": {"type": "integer"},
                "page_size": {"type": "integer"},
                "total_pages": {"type": "integer"},
            },
            "additionalProperties": True,
        },
        "data": {},
        "error": {"type": "string"},
        "message": {"type": "string"},
    },
    "additionalProperties": True,
}

ERROR_ENVELOPE_SCHEMA = {
    "allOf": [
        BASE_ENVELOPE_SCHEMA,
        {
            "type": "object",
            "required": ["ok", "error", "message"],
            "properties": {
                "ok": {"const": False},
                "error": {"type": "string"},
                "message": {"type": "string"},
            },
        },
    ]
}

REQUEST_SCHEMAS = {
    "none": {"description": "No request body required"},
    "update": {
        "type": "object",
        "properties": {
            "force": {"type": "boolean"},
            "update_type": {"type": "string", "enum": ["realtime", "planning", "all"]},
            "clear_cache": {"type": "boolean"},
        },
        "required": ["force"],
        "additionalProperties": False,
    },
}


def _envelope_with_data(data_description: str):
    schema = deepcopy(BASE_ENVELOPE_SCHEMA)
    schema["properties"]["data"] = {
        "description": data_description,
    }
    return schema


ENDPOINT_SCHEMAS = {
    "index": {
        "method": "GET",
        "path": "/api/",
        "description": "API index with quick links",
        "request_schema": REQUEST_SCHEMAS["none"],
        "response_schema": _envelope_with_data("API index object"),
    },
    "health": {
        "method": "GET",
        "path": "/api/health",
        "description": "Health status",
        "request_schema": REQUEST_SCHEMAS["none"],
        "response_schema": _envelope_with_data("Health payload"),
    },
    "realtime_data": {
        "method": "GET",
        "path": "/api/realtime/data",
        "description": "Real-time train data",
        "request_schema": REQUEST_SCHEMAS["none"],
        "response_schema": _envelope_with_data("GTFS realtime payload in data field"),
    },
    "planning_files": {
        "method": "GET",
        "path": "/api/planningdata/files",
        "description": "Available planning files",
        "request_schema": REQUEST_SCHEMAS["none"],
        "response_schema": _envelope_with_data("Array of planning filenames"),
    },
    "planning_file": {
        "method": "GET",
        "path": "/api/planningdata/<filename>",
        "description": "Planning data with pagination/filtering",
        "request_schema": REQUEST_SCHEMAS["none"],
        "response_schema": _envelope_with_data("Paginated planning rows"),
    },
    "cache_index": {
        "method": "GET",
        "path": "/api/cache",
        "description": "List available cache payloads",
        "request_schema": REQUEST_SCHEMAS["none"],
        "response_schema": _envelope_with_data("Cache metadata index"),
    },
    "cache_item": {
        "method": "GET",
        "path": "/api/cache/<data_type>",
        "description": "Fetch cache payload by type",
        "request_schema": REQUEST_SCHEMAS["none"],
        "response_schema": _envelope_with_data("Cached payload for requested type"),
    },
    "trajectories": {
        "method": "GET",
        "path": "/api/trajectories",
        "description": "Combined trajectory data",
        "request_schema": REQUEST_SCHEMAS["none"],
        "response_schema": _envelope_with_data("Trajectory records"),
    },
    "security_audit": {
        "method": "GET",
        "path": "/api/security/audit",
        "description": "Security checks/audit result",
        "request_schema": REQUEST_SCHEMAS["none"],
        "response_schema": _envelope_with_data("Security audit object"),
    },
    "update": {
        "method": "POST",
        "path": "/api/update",
        "description": "Force data refresh",
        "request_schema": REQUEST_SCHEMAS["update"],
        "response_schema": _envelope_with_data("Update execution result"),
        "error_schema": ERROR_ENVELOPE_SCHEMA,
    },
}


def get_schema_catalog(base_url: str = ""):
    endpoint_ids = sorted(ENDPOINT_SCHEMAS.keys())
    return {
        "spec_name": f"{API_NAME} Schema Catalog",
        "spec_type": "json-schema-catalog",
        "schema_spec_version": SCHEMA_SPEC_VERSION,
        "api_version": API_VERSION,
        "base_url": base_url,
        "endpoints": endpoint_ids,
        "components": {
            "base_envelope": BASE_ENVELOPE_SCHEMA,
            "error_envelope": ERROR_ENVELOPE_SCHEMA,
        },
        "links": {
            schema_id: f"{base_url}/api/schema/{schema_id}" if base_url else f"/api/schema/{schema_id}"
            for schema_id in endpoint_ids
        },
    }


def get_endpoint_schema(schema_id: str):
    return ENDPOINT_SCHEMAS.get(schema_id)


def get_all_endpoint_schemas():
    return deepcopy(ENDPOINT_SCHEMAS)
