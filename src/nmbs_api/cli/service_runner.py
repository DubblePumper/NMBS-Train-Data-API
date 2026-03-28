#!/usr/bin/env python3
"""Standalone NMBS data collection service CLI."""

import argparse
import time
from datetime import datetime

from nmbs_api.data_service import NMBSDataService
from nmbs_api.utils.logging.logging_utils import setup_logging, get_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='NMBS Data Collection Service')
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Interval in seconds between data downloads (default: 60)',
    )
    parser.add_argument(
        '--scrape-interval',
        type=int,
        default=86400,
        help='Interval in seconds between website scraping (default: 86400 - once per day)',
    )
    parser.add_argument(
        '--log-file',
        type=str,
        default='logs/nmbs_service.log',
        help='Path to log file (default: logs/nmbs_service.log)',
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data',
        help='Directory to store data files (default: data)',
    )
    parser.add_argument('--no-colors', action='store_true', help='Disable colored output in console')
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(log_file=args.log_file, use_colors=not args.no_colors)
    logger = get_logger("nmbs_service")

    logger.info(f"Starting NMBS Data Collection Service - {datetime.now().isoformat()}")
    logger.info(f"Data download interval: {args.interval} seconds")
    logger.info(f"Website scraping interval: {args.scrape_interval} seconds")
    logger.info(f"Data directory: {args.data_dir}")

    service = NMBSDataService(cache_dir=args.data_dir)
    last_scrape_time = 0

    try:
        with logger.group("Initial Data Collection"):
            logger.info("Performing initial website scrape...")
            service.scrape_website()
            last_scrape_time = time.time()

            logger.info("Downloading initial data...")
            service.download_data()

        logger.info("Service running. Press Ctrl+C to stop.")
        while True:
            current_time = time.time()
            if current_time - last_scrape_time >= args.scrape_interval:
                with logger.group("Scheduled Website Scrape"):
                    logger.info("Scraping website for updates...")
                    service.scrape_website()
                    last_scrape_time = current_time

            with logger.group("Data Download"):
                service.download_data()

            time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("Service stopped by user.")
    except Exception as exc:
        logger.error(f"Service error: {str(exc)}")
        raise
    finally:
        logger.info("Service shutting down.")


if __name__ == "__main__":
    main()
