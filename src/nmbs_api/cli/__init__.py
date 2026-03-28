"""CLI entrypoints for NMBS Train Data API."""

from .service_runner import main as run_data_service
from .web_runner import main as run_web_api

__all__ = ["run_data_service", "run_web_api"]
