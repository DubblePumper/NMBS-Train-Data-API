"""
Test utilities for NMBS Train Data API

This module contains common utilities used across all tests.
"""
import os
import time
import json
import requests
from enum import Enum
from typing import Dict, List, Any, Tuple, Optional, Union
import logging
from datetime import datetime
import functools
from colorama import Fore, Back, Style, init

# Initialize colorama
init(autoreset=True)

# API base URL (default for local testing)
API_BASE_URL = os.environ.get('API_TEST_URL', 'http://localhost:25580')

# Test statuses
class TestStatus(Enum):
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'
    INFO = 'INFO'


# Prevent pytest from trying to collect this Enum as a test class.
TestStatus.__test__ = False

# Color settings for different test statuses
TEST_COLORS = {
    TestStatus.RUNNING: Fore.BLUE + Style.BRIGHT,
    TestStatus.SUCCESS: Fore.GREEN + Style.BRIGHT,
    TestStatus.FAILED: Fore.RED + Style.BRIGHT,
    TestStatus.SKIPPED: Fore.YELLOW + Style.BRIGHT,
    TestStatus.INFO: Fore.CYAN,
}

# Separator styles
HEADER_SEPARATOR = f"{Fore.MAGENTA}{Style.BRIGHT}{'═' * 80}{Style.RESET_ALL}"
SECTION_SEPARATOR = f"{Fore.CYAN}{'─' * 80}{Style.RESET_ALL}"
TEST_SEPARATOR = f"{Fore.BLUE}{'·' * 60}{Style.RESET_ALL}"

# Get logger
logger = logging.getLogger("nmbs_api.tests")

def format_status_message(status: TestStatus, message: str) -> str:
    """Format a message with the appropriate color based on status"""
    color = TEST_COLORS.get(status, '')
    return f"{color}{message}{Style.RESET_ALL}"

def log_test(test_name: str, status: TestStatus, message: str = "", exception: Exception = None, data_count: int = None) -> None:
    """Log a test result with consistent formatting and colors"""
    status_str = status.value
    color = TEST_COLORS.get(status, '')
    
    # Format the test name for better readability
    formatted_name = test_name.replace('test_', '').replace('_', ' ').title()
    
    if status == TestStatus.RUNNING:
        logger.info(format_status_message(status, f"▶ Running: {formatted_name} {message}"))
    elif status == TestStatus.SUCCESS:
        success_msg = f"✓ Success: {formatted_name}"
        if message:
            success_msg += f" - {message}"
        if data_count is not None:
            success_msg += f" [{data_count} records]"
        logger.info(format_status_message(status, success_msg))
    elif status == TestStatus.FAILED:
        error_msg = f"✗ Failed: {formatted_name}"
        if message:
            error_msg += f" - {message}"
        if exception:
            error_msg += f" [{str(exception)}]"
        logger.error(format_status_message(status, error_msg))
    elif status == TestStatus.SKIPPED:
        logger.warning(format_status_message(status, f"⚠ Skipped: {formatted_name} - {message}"))
    elif status == TestStatus.INFO:
        logger.info(format_status_message(status, f"ℹ {formatted_name} - {message}"))

def log_section(title: str):
    """Log a section header with separator lines"""
    logger.info(SECTION_SEPARATOR)
    logger.info(format_status_message(TestStatus.INFO, f"▶ {title}"))
    logger.info(SECTION_SEPARATOR)

def timed_test(func):
    """Decorator to measure and log test execution time"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(format_status_message(
                TestStatus.INFO, 
                f"⌛ '{func.__name__}' completed in {elapsed:.2f} seconds"
            ))
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(format_status_message(
                TestStatus.FAILED, 
                f"⌛ '{func.__name__}' failed after {elapsed:.2f} seconds: {str(e)}"
            ))
            raise
    return wrapper

def make_api_request(endpoint: str, method: str = 'GET', data: Dict = None, timeout: int = 10, retries: int = 3, retry_delay: float = 2.0) -> Tuple[int, Any]:
    """
    Make an API request and return the status code and response data
    
    Args:
        endpoint: API endpoint path (without base URL)
        method: HTTP method (GET, POST, etc.)
        data: Request data for POST requests
        timeout: Request timeout in seconds
        retries: Number of retry attempts if connection fails
        retry_delay: Delay between retry attempts in seconds
        
    Returns:
        Tuple of (status_code, response_data)
    """
    url = f"{API_BASE_URL}/{endpoint.lstrip('/')}"

    for attempt in range(retries):
        try:
            if method.upper() == 'GET':
                response = requests.get(url, timeout=timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            status_code = response.status_code
            
            # Try to parse JSON response
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = response.text
                
            return status_code, response_data
        
        except requests.exceptions.ConnectionError as e:
            if attempt < retries - 1:
                logger.warning(f"Connection failed (attempt {attempt + 1}/{retries}), retrying in {retry_delay} seconds: {str(e)}")
                time.sleep(retry_delay)
            else:
                logger.error(f"API request failed after {retries} attempts: {str(e)}")
                return 0, str(e)
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return 0, str(e)

def get_data_count(response_data: Any) -> int:
    """
    Get the count of records from a response
    
    Args:
        response_data: Response data from API
        
    Returns:
        Count of records or 0 if not countable
    """
    try:
        if isinstance(response_data, dict):
            if "data" in response_data and isinstance(response_data["data"], list):
                return len(response_data["data"])
            elif "pagination" in response_data and "totalRecords" in response_data["pagination"]:
                return response_data["pagination"]["totalRecords"]
            else:
                # Count top-level keys as a fallback
                return len(response_data)
        elif isinstance(response_data, list):
            return len(response_data)
        else:
            return 0
    except Exception:
        return 0