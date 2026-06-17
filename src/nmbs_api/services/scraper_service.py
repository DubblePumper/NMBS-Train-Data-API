import logging
import os

from dotenv import load_dotenv

from .base_service import BaseService

logger = logging.getLogger(__name__)

load_dotenv()


DEFAULT_GTFS_SCHEDULE_URL = "https://api-management-discovery-production.azure-api.net/api/gtfs/feed/nmbssncb/static"
DEFAULT_GTFS_RT_TRIP_UPDATES_URL = "https://api-management-discovery-production.azure-api.net/api/gtfs/feed/nmbssncb/rt/trip-update"
DEFAULT_GTFS_RT_SERVICE_ALERTS_URL = "https://api-management-discovery-production.azure-api.net/api/gtfs/feed/nmbssncb/rt/alert"
DEFAULT_NETEX_EPIP_URL = "https://belgianmobility.blob.core.windows.net/epip-production/epip-nmbssncb-bmc-latest.xml"


class ScraperService(BaseService):
    """
    Compatibility service that resolves official Belgian Mobility feed URLs.

    The old implementation scraped the NMBS website and maintained fallback
    URLs. Belgian Mobility now publishes direct GTFS/GTFS-RT/NeTEx feeds, so
    this service only materializes configured feed URLs into the existing cache
    files for the downloader and parser.
    """

    def __init__(self, cache_dir="data", use_proxy=False):
        super().__init__(cache_dir)
        self.use_proxy = use_proxy
        if use_proxy:
            logger.warning("Proxy settings are ignored for official feed downloads")

        self._load_urls()
        self._load_planning_urls()
        self.configure_urls(save=False)

    @property
    def gtfs_schedule_url(self):
        return os.getenv("NMBS_DATA_URL", DEFAULT_GTFS_SCHEDULE_URL)

    @property
    def gtfs_rt_trip_updates_url(self):
        return os.getenv("NMBS_REALTIME_TRIP_UPDATES_URL", DEFAULT_GTFS_RT_TRIP_UPDATES_URL)

    @property
    def gtfs_rt_service_alerts_url(self):
        return os.getenv("NMBS_REALTIME_SERVICE_ALERTS_URL", DEFAULT_GTFS_RT_SERVICE_ALERTS_URL)

    @property
    def netex_epip_url(self):
        return os.getenv("NMBS_NETEX_URL", DEFAULT_NETEX_EPIP_URL)

    def configure_urls(self, save=True):
        """Configure feed URLs from environment variables and official defaults."""
        self.urls = {
            "trip_updates": {
                "url": self.gtfs_rt_trip_updates_url,
                "filename": "NMBS_realtime_trip_updates.bin",
                "feed_type": "trip_updates",
                "last_checked": self.get_timestamp(),
            },
            "service_alerts": {
                "url": self.gtfs_rt_service_alerts_url,
                "filename": "NMBS_realtime_service_alerts.bin",
                "feed_type": "service_alerts",
                "last_checked": self.get_timestamp(),
            },
        }

        self.planning_urls = {
            "gtfs_schedule": {
                "url": self.gtfs_schedule_url,
                "filename": "NMBS_GTFS_Schedule.zip",
                "feed_type": "gtfs_schedule",
                "last_checked": self.get_timestamp(),
            }
        }

        if save:
            self._save_urls()
            self._save_planning_urls()

        return True

    def scrape_website(self):
        """
        Backwards-compatible entry point.

        No website scraping is performed. Calling this refreshes the cached feed
        URL metadata from .env and the Belgian Mobility official defaults.
        """
        logger.info("Configuring official Belgian Mobility feed URLs")
        return self.configure_urls(save=True)

    def get_request_headers(self, accept=None):
        """Build request headers for Belgian Mobility endpoints."""
        headers = {
            "User-Agent": os.getenv("NMBS_API_USER_AGENT", "nmbs-train-data-api/0.2"),
        }

        if accept:
            headers["Accept"] = accept

        api_key = os.getenv("BM_API_KEY")
        if api_key:
            header_name = os.getenv("BM_API_KEY_HEADER", "Ocp-Apim-Subscription-Key")
            headers[header_name] = api_key

        return headers

    def save_cookies(self):
        """Deprecated no-op kept for callers from older versions."""
        logger.info("Cookies are no longer used for official feed downloads")
        return True

    def get_realtime_url(self):
        """Get the trip updates URL for backwards compatibility."""
        self.configure_urls(save=False)
        return self.urls["trip_updates"]["url"]

    def get_realtime_urls(self):
        """Get all official realtime feed URLs."""
        self.configure_urls(save=False)
        return self.urls

    def get_planning_url(self):
        """Get the official GTFS Schedule URL."""
        self.configure_urls(save=False)
        return self.planning_urls["gtfs_schedule"]["url"]

    def get_netex_url(self):
        """Get the optional NeTEx EPIP URL."""
        return self.netex_epip_url
