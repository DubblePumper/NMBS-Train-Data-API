"""
NMBS Data Service - Main Module

This is a refactored version of the NMBS Data Service using a modular architecture
for better maintainability and separation of concerns.

The original monolithic service has been split into specialized services:
- BaseService: Common functionality for all services
- ScraperService: Official Belgian Mobility feed URL resolution
- DownloaderService: Downloading data files
- ParserService: Parsing and filtering data files
- DataService: Main service integrating the others

This file acts as the main entry point for backward compatibility.
"""

import logging
from .services.data_service import DataService

# Configure logging
logger = logging.getLogger(__name__)

# Create a singleton instance for the API
_data_service = None

def get_data_service():
    """
    Get or create the NMBSDataService singleton
    """
    global _data_service
    if _data_service is None:
        _data_service = DataService()
    return _data_service

# Expose the main classes for backward compatibility
NMBSDataService = DataService
