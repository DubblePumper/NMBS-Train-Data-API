import logging
import threading
import schedule
import time
import os
from dotenv import load_dotenv
from .base_service import BaseService
from .scraper_service import ScraperService
from .downloader_service import DownloaderService
from .parser_service import ParserService

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class DataService(BaseService):
    """
    Main service to efficiently manage NMBS data retrieval and access
    
    This service integrates the specialized components:
    1. ScraperService - Resolves official Belgian Mobility feed URLs
    2. DownloaderService - Downloads the actual data files (realtime, planning and optional NeTEx)
    3. ParserService - Parses and filters the data files for API access
    """
    
    def __init__(self, cache_dir='data', use_proxy=False):
        super().__init__(cache_dir)
        
        # Initialize the specialized services
        self.scraper = ScraperService(cache_dir, use_proxy)
        self.downloader = DownloaderService(cache_dir, self.scraper)
        self.parser = ParserService(cache_dir)
        
        # Service state
        self._service_thread = None
    
    def scrape_website(self):
        """
        Refresh official feed URL metadata.

        Kept for backwards compatibility with older callers; no website
        scraping is performed.
        """
        return self.scraper.scrape_website()
    
    def download_data(self, force=False, update_type="all"):
        """
        Download the latest data files using official feed URLs.
        """
        return self.downloader.download_data(force=force, update_type=update_type)
    
    def get_latest_realtime_data(self):
        """
        Get the latest realtime data
        
        Returns:
            dict: The latest GTFS real-time data as a dictionary
        """
        return self.parser.get_latest_realtime_data()
    
    def get_planning_files_list(self):
        """
        Get a list of available planning data files
        
        Returns:
            list: A list of the available planning data files
        """
        return self.parser.get_planning_data_list()
    
    def get_planning_data_file(self, filename, page=0, page_size=1000, search_params=None):
        """
        Get a specific planning data file content with enhanced filtering capabilities
        
        Args:
            filename: The name of the file to get
            page: The page number to get (0-based, default: 0)
            page_size: The number of records per page (default: 1000)
            search_params: Optional dictionary with search parameters:
                {
                    'search': {'query': str, 'field': str},
                    'filters': {'field_name': 'value'},
                    'sort': {'field': str, 'direction': 'asc'|'desc'}
                }
        """
        return self.parser.get_planning_data_file(filename, page, page_size, search_params)
    
    def run_as_service(self):
        """
        Run the data service with scheduled tasks
        """
        # Refresh configured feed URLs once per day.
        schedule.every().day.at("03:00").do(self.scrape_website)
        
        # Realtime downloads run frequently; static data is throttled by DownloaderService.
        schedule.every(30).seconds.do(self.download_data)
        
        # Initial run to ensure we have data right away
        if not self.scraper.urls or not self.scraper.planning_urls:
            logger.info("Initiële feed URL configuratie...")
            self.scrape_website()
        
        logger.info("Initiële data download...")
        self.download_data()
        
        logger.info("NMBS Data Service is gestart. Druk Ctrl+C om te stoppen.")
        
        # Run the scheduler in a loop
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Service wordt gestopt...")
    
    def start_background_service(self):
        """
        Start the data service in a background thread
        Returns:
            threading.Thread: The background thread running the service
        """
        if self._service_thread is None or not self._service_thread.is_alive():
            self._service_thread = threading.Thread(target=self.run_as_service, daemon=True)
            self._service_thread.start()
            logger.info("Data service gestart in achtergrond thread")
        else:
            logger.info("Data service draait al in achtergrond thread")
            
        return self._service_thread
    
    # Backwards compatibility for old API
    def get_latest_data(self, include_track_changes=True):
        """
        [DEPRECATED] Use get_latest_realtime_data() instead
        API method to get the latest realtime data
        """
        return self.get_latest_realtime_data()
