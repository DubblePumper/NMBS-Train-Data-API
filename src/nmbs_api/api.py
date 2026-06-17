import os
import json
from .data_service import NMBSDataService

# Singleton instance of the data service
_data_service = None

def get_data_service():
    """
    Get or create the NMBSDataService singleton
    """
    global _data_service
    if _data_service is None:
        _data_service = NMBSDataService()
    return _data_service

def start_data_service():
    """
    Start the NMBS data service in the background
    
    This will:
    1. Configure official Belgian Mobility feed URLs
    2. Download the latest data files
    3. Keep running in the background to update the data regularly
    
    Returns:
        threading.Thread: The background thread running the service
    """
    service = get_data_service()
    return service.start_background_service()

def get_realtime_data():
    """
    Get the latest real-time NMBS data with track changes
    
    Returns:
        dict: The GTFS real-time data as a dictionary
    """
    service = get_data_service()
    return service.get_latest_realtime_data()

def get_planning_files_list():
    """
    Get a list of available planning data files
    
    Returns:
        list: List of available planning files
    """
    service = get_data_service()
    return service.get_planning_files_list()

def get_planning_file(filename, page=0, page_size=1000, search_params=None):
    """
    Get the content of a specific planning file
    
    Args:
        filename (str): Name of the file to get
        page (int): Page number (0-based) for paginated results
        page_size (int): Number of records per page
        search_params (dict): Optional search parameters to filter results
            {
                'search': {'query': str, 'field': str},
                'filters': {'field_name': 'value'},
                'sort': {'field': str, 'direction': 'asc'|'desc'}
            }
    
    Returns:
        dict/list/str: The file content parsed as appropriate
    """
    service = get_data_service()
    # Call the enhanced get_planning_data_file method with all parameters
    return service.get_planning_data_file(filename, page, page_size, search_params)

def force_update(force=True, update_type="all"):
    """
    Force an immediate update of the data
    
    Returns:
        bool: True if successful
    """
    service = get_data_service()
    return service.download_data(force=force, update_type=update_type)

# Backwards compatibility for old API
def get_latest_data(include_track_changes=True):
    """
    [DEPRECATED] Use get_realtime_data() instead
    Get the latest real-time NMBS data
    
    Args:
        include_track_changes (bool): Whether to include track change information
        
    Returns:
        dict: The GTFS real-time data as a dictionary
    """
    return get_realtime_data()
