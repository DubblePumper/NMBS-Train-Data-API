# Repository Structure

This project is organized with centralized application code in `src/nmbs_api`.

## Canonical code locations

- `src/nmbs_api/cli/` — CLI entrypoints (`nmbs-data-service`, `nmbs-web-api`)
- `src/nmbs_api/search/` — Search engine module
- `src/nmbs_api/services/` — Data acquisition/parsing services
- `src/nmbs_api/web/` — Web API app, middleware, routes, security
- `src/nmbs_api/web/schemas.py` — Versioned API schema catalog for clients
- `src/nmbs_api/tests/` — Test modules

## Root runtime entrypoint

The only root startup file is:

- `start.py`

All application logic remains centralized under `src/nmbs_api/`.
