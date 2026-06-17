import json
import logging
import os
import time
import traceback
import zipfile

import requests
from google.protobuf.json_format import MessageToDict
from google.transit import gtfs_realtime_pb2

from .base_service import BaseService
from .scraper_service import ScraperService

logger = logging.getLogger(__name__)


class DownloaderService(BaseService):
    """Download official Belgian Mobility GTFS, GTFS-RT and NeTEx files."""

    def __init__(self, cache_dir="data", feed_source=None):
        super().__init__(cache_dir)
        self.feed_source = feed_source or ScraperService(cache_dir)
        self.session = requests.Session()
        self.timeout = int(os.getenv("NMBS_DOWNLOAD_TIMEOUT", "60"))
        self.planning_interval = int(os.getenv("PLANNING_INTERVAL", "86400"))
        self.netex_interval = int(os.getenv("NETEX_INTERVAL", "86400"))

    def download_data(self, force=False, update_type="all"):
        """
        Download the latest official feeds.

        Realtime feeds are refreshed on every call. Static GTFS and NeTEx are
        downloaded only when stale unless force=True.
        """
        update_type = update_type or "all"
        success = False

        if update_type in ("all", "realtime"):
            success = self.download_realtime_data() or success

        if update_type in ("all", "planning"):
            success = self.download_planning_data(force=force) or success

        if update_type == "netex" or (update_type == "all" and self._netex_enabled()):
            success = self.download_netex_data(force=force) or success

        return success

    def download_realtime_data(self):
        """Download GTFS-Realtime trip updates and service alerts."""
        return self._download_realtime_data()

    def download_planning_data(self, force=False):
        """Download and extract the GTFS Schedule ZIP."""
        return self._download_planning_data(force=force)

    def download_netex_data(self, force=False):
        """Download the optional NeTEx EPIP XML export."""
        return self._download_netex_data(force=force)

    def _request(self, url, accept=None):
        headers = self.feed_source.get_request_headers(accept=accept)
        response = self.session.get(url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response

    def _download_realtime_data(self):
        self.feed_source.configure_urls(save=True)
        successful_downloads = 0
        update_info = {}

        for name, info in self.feed_source.urls.items():
            url = info["url"]
            filename = info["filename"]
            output_path = os.path.join(self.realtime_dir, filename)
            logger.info(f"Downloading GTFS-RT {name} from {url}")

            try:
                response = self._request(url, accept="application/x-protobuf")

                with open(output_path, "wb") as f:
                    f.write(response.content)

                feed_dict, source_format = self._decode_realtime_response(response)

                json_file = output_path.replace(".bin", ".json")
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(feed_dict, f, indent=2)

                successful_downloads += 1
                update_info[name] = {
                    "last_downloaded": self.get_timestamp(),
                    "bin_file": output_path,
                    "json_file": json_file,
                    "source_url": url,
                    "feed_type": info.get("feed_type", name),
                    "source_format": source_format,
                    "content_length": response.headers.get("Content-Length"),
                }
                logger.info(f"Downloaded and converted GTFS-RT {name}: {output_path}")
            except Exception as e:
                logger.error(f"Failed to download GTFS-RT {name}: {str(e)}")
                logger.error(traceback.format_exc())

        if update_info:
            self._write_json(self.last_updated_file, update_info)

        return successful_downloads > 0

    def _download_planning_data(self, force=False):
        self.feed_source.configure_urls(save=True)

        if not force and not self._is_stale(self.planning_updated_file, self.planning_interval):
            logger.info("GTFS Schedule data is still fresh; skipping download")
            return True

        successful_downloads = 0
        update_info = {}

        for name, info in self.feed_source.planning_urls.items():
            url = info["url"]
            filename = info["filename"]
            output_path = os.path.join(self.planning_dir, filename)
            logger.info(f"Downloading GTFS Schedule {name} from {url}")

            try:
                response = self._request(url, accept="application/zip,application/octet-stream,*/*")

                with open(output_path, "wb") as f:
                    f.write(response.content)

                if self._extract_planning_zip(output_path):
                    extracted_files = os.listdir(self.planning_extracted_dir)
                    update_info[name] = {
                        "last_downloaded": self.get_timestamp(),
                        "zip_file": output_path,
                        "extracted_dir": self.planning_extracted_dir,
                        "extracted_files": extracted_files,
                        "source_url": url,
                        "content_type": response.headers.get("Content-Type"),
                        "content_length": response.headers.get("Content-Length"),
                    }
                    successful_downloads += 1
                    logger.info(f"Downloaded and extracted GTFS Schedule: {output_path}")
            except Exception as e:
                logger.error(f"Failed to download GTFS Schedule {name}: {str(e)}")
                logger.error(traceback.format_exc())

        if update_info:
            self._write_json(self.planning_updated_file, update_info)

        return successful_downloads > 0

    def _download_netex_data(self, force=False):
        if not force and not self._is_stale(self.netex_updated_file, self.netex_interval):
            logger.info("NeTEx EPIP data is still fresh; skipping download")
            return True

        url = self.feed_source.get_netex_url()
        output_path = os.path.join(self.netex_dir, "NMBS_NeTEx_EPIP.xml")
        logger.info(f"Downloading NeTEx EPIP from {url}")

        try:
            response = self._request(url, accept="application/xml,text/xml,*/*")
            with open(output_path, "wb") as f:
                f.write(response.content)

            update_info = {
                "netex_epip": {
                    "last_downloaded": self.get_timestamp(),
                    "xml_file": output_path,
                    "source_url": url,
                    "content_type": response.headers.get("Content-Type"),
                    "content_length": response.headers.get("Content-Length"),
                }
            }
            self._write_json(self.netex_updated_file, update_info)
            return True
        except Exception as e:
            logger.error(f"Failed to download NeTEx EPIP: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def _decode_realtime_response(self, response):
        content_type = response.headers.get("Content-Type", "").lower()
        content = response.content

        if "json" in content_type or content.lstrip().startswith(b"{"):
            return response.json(), "json"

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(content)
        return MessageToDict(feed), "protobuf"

    def _extract_planning_zip(self, zip_path):
        """Extract the planning data ZIP file."""
        logger.info(f"Extracting ZIP file: {zip_path}")

        try:
            file_size = os.path.getsize(zip_path)
            if file_size < 100:
                logger.error(f"ZIP file is too small ({file_size} bytes)")
                return False

            for file in os.listdir(self.planning_extracted_dir):
                file_path = os.path.join(self.planning_extracted_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                file_names = zip_ref.namelist()
                if not file_names:
                    logger.error("ZIP file contains no files")
                    return False

                for file_name in file_names:
                    target_path = os.path.abspath(os.path.join(self.planning_extracted_dir, file_name))
                    extracted_root = os.path.abspath(self.planning_extracted_dir)
                    if not target_path.startswith(extracted_root + os.sep):
                        logger.warning(f"Skipping unsafe ZIP member: {file_name}")
                        continue
                    zip_ref.extract(file_name, path=self.planning_extracted_dir)

            extracted_files = os.listdir(self.planning_extracted_dir)
            required_files = ["stops.txt", "routes.txt", "trips.txt", "stop_times.txt"]
            for required_file in required_files:
                if required_file not in extracted_files:
                    logger.warning(f"Required GTFS file missing after extraction: {required_file}")

            if not extracted_files:
                logger.error(f"No files extracted to: {self.planning_extracted_dir}")
                return False

            return True
        except zipfile.BadZipFile:
            logger.error(f"Invalid ZIP file: {zip_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to extract ZIP file: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def _is_stale(self, update_file, interval_seconds):
        if not os.path.exists(update_file):
            return True

        try:
            modified_at = os.path.getmtime(update_file)
            return (time.time() - modified_at) >= interval_seconds
        except OSError:
            return True

    def _netex_enabled(self):
        return os.getenv("NMBS_NETEX_ENABLED", "false").lower() in ("1", "true", "yes", "on")

    def _write_json(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write JSON file {path}: {str(e)}")
