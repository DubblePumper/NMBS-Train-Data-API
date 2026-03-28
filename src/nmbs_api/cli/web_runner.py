#!/usr/bin/env python3
"""Web API runner CLI for NMBS Train Data API."""

import argparse
import logging
import os
import sys
import threading
import time
from datetime import datetime

from dotenv import load_dotenv

from nmbs_api.data_service import NMBSDataService
from nmbs_api.tests.test_runner import run_all_tests
from nmbs_api.utils.logging.logging_utils import get_logger, setup_logging
from nmbs_api.web_api import start_web_server

load_dotenv()

data_download_complete = threading.Event()


def generate_log_filename() -> str:
    """Generate a unique log filename with timestamp."""
    logs_dir = os.path.join(os.getcwd(), 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    current_time = datetime.now()
    date_str = current_time.strftime("%Y-%m-%d")
    timestamp = current_time.strftime("%H-%M-%S")
    return os.path.join(logs_dir, f"NmbsAPI_{date_str}_{timestamp}.log")


def run_data_service(interval: int, scrape_interval: int, data_dir: str, logger) -> None:
    """Run the NMBS data collection service in a separate thread."""
    logger.info(f"Starting NMBS Data Collection Service - {datetime.now().isoformat()}")
    logger.info(f"Data download interval: {interval} seconds")
    logger.info(f"Website scraping interval: {scrape_interval} seconds")
    logger.info(f"Data directory: {data_dir}")

    service = NMBSDataService(cache_dir=data_dir)
    last_scrape_time = 0

    try:
        with logger.group("Initial Data Collection"):
            logger.info("Performing initial website scrape...")
            service.scrape_website()
            last_scrape_time = time.time()

            logger.info("Downloading initial data...")
            success = service.download_data()

            if not success:
                logger.warning("Initial data download was not successful")
            else:
                logger.info("Initial data download completed successfully!")

            data_download_complete.set()

        logger.info("Data service running in background.")
        while True:
            current_time = time.time()
            if current_time - last_scrape_time >= scrape_interval:
                with logger.group("Scheduled Website Scrape"):
                    logger.info("Scraping website for updates...")
                    service.scrape_website()
                    last_scrape_time = current_time

            with logger.group("Data Download"):
                service.download_data()

            time.sleep(interval)

    except Exception as exc:
        logger.error(f"Data service error: {str(exc)}")
        if not data_download_complete.is_set():
            data_download_complete.set()
        raise


def run_tests_with_retry(logger, max_retries: int = 5, retry_delay: int = 5):
    """Run tests with retry mechanism to ensure API is available."""
    logger.info("Starting test execution with retry mechanism")

    for attempt in range(max_retries):
        try:
            logger.info(f"Test attempt {attempt + 1}/{max_retries}")
            results = run_all_tests()
            success_rate = results['success'] / results['total'] if results['total'] > 0 else 0
            logger.info(f"Tests completed: {results['success']}/{results['total']} passed ({success_rate:.0%})")

            if results['failed'] == 0:
                logger.info("All tests passed successfully!")
                return results

            logger.warning(f"Some tests failed: {results['failed']}/{results['total']}")
            if attempt < max_retries - 1:
                logger.info(f"Waiting {retry_delay} seconds before retrying tests...")
                time.sleep(retry_delay)

        except Exception as exc:
            logger.error(f"Error running tests: {str(exc)}")
            if attempt < max_retries - 1:
                logger.info(f"Waiting {retry_delay} seconds before retrying...")
                time.sleep(retry_delay)

    logger.error(f"Tests still failing after {max_retries} attempts")
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Run NMBS Web API and optional data service')

    parser.add_argument('--host', type=str, default=os.getenv('API_HOST', '127.0.0.1'), help='Host to run the web API on')
    parser.add_argument('--port', type=int, default=int(os.getenv('API_PORT', 25580)), help='Port to run the web API on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')

    parser.add_argument('--with-data-service', action='store_true', help='Also run the data collection service')
    parser.add_argument('--data-interval', type=int, default=int(os.getenv('DATA_INTERVAL', 60)), help='Interval in seconds between data downloads (default: 60)')
    parser.add_argument('--scrape-interval', type=int, default=int(os.getenv('SCRAPE_INTERVAL', 86400)), help='Interval in seconds between website scraping (default: 86400 - once per day)')
    parser.add_argument('--data-dir', type=str, default=os.getenv('DATA_DIR', 'data'), help='Directory to store data files (default: data)')
    parser.add_argument('--verbose', action='store_true', help='Show INFO level logs in the console')
    parser.add_argument('--no-colors', action='store_true', help='Disable colored output in console')

    parser.add_argument('--no-tests', action='store_true', help='Skip running tests completely')
    parser.add_argument('--test-delay', type=int, default=int(os.getenv('TEST_DELAY', 10)), help='Additional delay in seconds before running tests after data download (default: 10)')
    parser.add_argument('--test-retries', type=int, default=int(os.getenv('TEST_RETRIES', 3)), help='Number of times to retry failed tests (default: 3)')
    parser.add_argument('--download-timeout', type=int, default=int(os.getenv('DOWNLOAD_TIMEOUT', 120)), help='Maximum time to wait for initial data download in seconds (default: 120)')

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    log_file = generate_log_filename()
    console_level = logging.INFO if args.verbose else logging.WARNING
    setup_logging(console_level=console_level, log_file=log_file, log_file_level=logging.WARNING, use_colors=not args.no_colors)
    logger = get_logger("nmbs_api")

    logger.info(f"Started NMBS Train Data API - {datetime.now().isoformat()}")
    logger.info(f"Logging warnings and errors to: {log_file}")

    data_download_complete.clear()

    if args.with_data_service:
        with logger.group("NMBS Train Data API Startup"):
            logger.info("Starting both data service and web API")
            data_thread = threading.Thread(
                target=run_data_service,
                args=(args.data_interval, args.scrape_interval, args.data_dir, logger),
                daemon=True,
            )
            data_thread.start()
            logger.info("Data service thread started")
    else:
        logger.info("Starting web API only (no data collection service)")
        logger.warning("Note: API needs data to function, make sure to run the data service separately if needed")
        data_download_complete.set()

    logger.info(f"Starting NMBS API on {args.host}:{args.port}")
    ssl_enabled = os.getenv('ENABLE_SSL', 'false').lower() == 'true'
    scheme = 'https' if ssl_enabled else 'http'
    logger.info(f"Access your API at: {scheme}://{args.host}:{args.port}/api/health")

    def run_api_server():
        start_web_server(host=args.host, port=args.port, debug=args.debug, start_background_service=False)

    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()

    time.sleep(5)

    if not args.no_tests:
        def run_delayed_tests():
            logger.info("Waiting for initial data download to complete before running tests...")
            download_success = data_download_complete.wait(timeout=args.download_timeout)
            if not download_success:
                logger.warning(f"Timed out waiting for data download after {args.download_timeout} seconds")

            logger.info(f"Data download completed. Waiting additional {args.test_delay} seconds before running tests...")
            time.sleep(args.test_delay)

            logger.info("Running tests now...")
            run_tests_with_retry(logger, max_retries=args.test_retries)

        test_thread = threading.Thread(target=run_delayed_tests, daemon=True)
        test_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down NMBS Train Data API")
        sys.exit(0)


if __name__ == '__main__':
    main()
