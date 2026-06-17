import os
import json
import logging
import traceback
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

class BaseService:
    """Base class for all NMBS data services, providing common functionality"""
    
    def __init__(self, cache_dir='data'):
        self.cache_dir = cache_dir
        self.realtime_dir = os.path.join(cache_dir, 'Real-time_gegevens')
        self.planning_dir = os.path.join(cache_dir, 'Planning_gegevens')
        self.netex_dir = os.path.join(cache_dir, 'NeTEx_EPIP')
        self.urls_file = os.path.join(self.realtime_dir, 'data_urls.json')
        self.planning_urls_file = os.path.join(self.planning_dir, 'planning_urls.json')
        self.last_updated_file = os.path.join(self.realtime_dir, 'last_updated.json')
        self.planning_updated_file = os.path.join(self.planning_dir, 'planning_updated.json')
        self.netex_updated_file = os.path.join(self.netex_dir, 'netex_updated.json')
        self.urls = {}
        self.planning_urls = {}
        
        # Create directories if they don't exist
        os.makedirs(self.realtime_dir, exist_ok=True)
        os.makedirs(self.planning_dir, exist_ok=True)
        os.makedirs(self.netex_dir, exist_ok=True)
        
        # Create subdirectories for extracted planning data
        self.planning_extracted_dir = os.path.join(self.planning_dir, 'extracted')
        os.makedirs(self.planning_extracted_dir, exist_ok=True)
    
    def _load_urls(self):
        """Load cached URLs from file"""
        if os.path.exists(self.urls_file):
            try:
                with open(self.urls_file, 'r') as f:
                    self.urls = json.load(f)
                    logger.info(f"Geladen URLs: {len(self.urls)} gevonden")
            except Exception as e:
                logger.error(f"Fout bij laden van URLs: {str(e)}")
                self.urls = {}
    
    def _save_urls(self):
        """Save URLs to cache file"""
        try:
            with open(self.urls_file, 'w') as f:
                json.dump(self.urls, f, indent=2)
            logger.info(f"URLs opgeslagen: {len(self.urls)}")
        except Exception as e:
            logger.error(f"Fout bij opslaan van URLs: {str(e)}")
    
    def _load_planning_urls(self):
        """Load cached planning URLs from file"""
        if os.path.exists(self.planning_urls_file):
            try:
                with open(self.planning_urls_file, 'r') as f:
                    self.planning_urls = json.load(f)
                    logger.info(f"Geladen planning URLs: {len(self.planning_urls)} gevonden")
            except Exception as e:
                logger.error(f"Fout bij laden van planning URLs: {str(e)}")
                self.planning_urls = {}
    
    def _save_planning_urls(self):
        """Save planning URLs to cache file"""
        try:
            with open(self.planning_urls_file, 'w') as f:
                json.dump(self.planning_urls, f, indent=2)
            logger.info(f"Planning URLs opgeslagen: {len(self.planning_urls)}")
        except Exception as e:
            logger.error(f"Fout bij opslaan van planning URLs: {str(e)}")
    
    def get_timestamp(self):
        """Get current timestamp in ISO format"""
        return datetime.now().isoformat()
