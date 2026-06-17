import os
import csv
import json
import logging
import traceback
import pandas as pd
import gc  # For garbage collection
import mmap  # For memory-mapped file access
from io import StringIO
from .base_service import BaseService

# Configure logging
logger = logging.getLogger(__name__)

class ParserService(BaseService):
    """Service to parse and filter NMBS data files"""
    
    def __init__(self, cache_dir='data'):
        super().__init__(cache_dir)
    
    def get_planning_data_list(self):
        """
        Get a list of available planning data files
        
        Returns:
            list: A list of the available planning data files
        """
        # Load planning updated info
        if not os.path.exists(self.planning_updated_file):
            logger.warning("Geen planning update info beschikbaar. Run download_data eerst.")
            return []
        
        try:
            with open(self.planning_updated_file, 'r') as f:
                update_info = json.load(f)
            
            # Get the list of files from the first available data
            if update_info:
                target_key = list(update_info.keys())[0]
                return update_info[target_key].get('extracted_files', [])
            else:
                logger.warning("Geen planning data info gevonden")
                return []
                
        except Exception as e:
            logger.error(f"Fout bij ophalen van planning bestandslijst: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def get_latest_realtime_data(self):
        """
        Get the latest realtime data
        
        Returns:
            dict: The latest GTFS real-time data as a dictionary
        """
        # Load last updated info
        if not os.path.exists(self.last_updated_file):
            logger.warning("Geen realtime update info beschikbaar. Run download_data eerst.")
            return None
        
        try:
            with open(self.last_updated_file, 'r') as f:
                update_info = json.load(f)
            
            if update_info:
                valid_keys = [key for key in update_info.keys() if not key.startswith('_')]
                
                if not valid_keys:
                    logger.warning("Geen geldige realtime data keys gevonden")
                    return None

                feeds = {}
                for target_key in valid_keys:
                    if not isinstance(update_info[target_key], dict) or 'json_file' not in update_info[target_key]:
                        logger.warning(f"Ongeldige realtime data structuur voor sleutel '{target_key}'")
                        continue

                    json_file = update_info[target_key]['json_file']
                    if os.path.exists(json_file):
                        with open(json_file, 'r') as f:
                            feeds[target_key] = json.load(f)
                    else:
                        logger.warning(f"Realtime JSON bestand niet gevonden: {json_file}")

                if not feeds:
                    return None

                if len(feeds) == 1:
                    return next(iter(feeds.values()))

                return {"feeds": feeds}
            else:
                logger.warning("Geen realtime data info gevonden")
                return None
                
        except Exception as e:
            logger.error(f"Fout bij ophalen van laatste realtime data: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
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
            
        Returns:
            dict/list: The file content as JSON (for CSV/TXT files)
            str: The file content as string (for other files)
            dict: A paginated response with metadata if pagination is used
        """
        file_path = os.path.join(self.planning_extracted_dir, filename)
        
        if not os.path.exists(file_path):
            logger.warning(f"Planning bestand niet gevonden: {file_path}")
            return None
        
        logger.info(f"Ophalen van planning bestand: {filename}")
        
        # Create default search params if none provided
        if search_params is None:
            search_params = {
                'search': {'query': None, 'field': None},
                'filters': {},
                'sort': {'field': None, 'direction': 'asc'}
            }
        
        try:
            # Determine file type and parse accordingly
            ext = os.path.splitext(filename)[1].lower()
            
            # For large files or stop_times.txt specifically, we need special handling
            if filename.lower() == 'stop_times.txt' or os.path.getsize(file_path) > 10*1024*1024:  # Files larger than 10MB
                logger.info(f"Groot bestand gedetecteerd: {filename}. Optimale verwerking wordt toegepast.")
                return self._parse_large_file_with_advanced_features(file_path, page, page_size, search_params)
            
            # For smaller files, we can load them completely and then filter
            # CSV files
            if ext == '.csv' or ext == '.txt':
                return self._parse_small_file_with_advanced_features(file_path, page, page_size, search_params)
            
            # CFG files and other non-structured data files
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
                
        except Exception as e:
            logger.error(f"Fout bij ophalen van planning bestand {filename}: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def _parse_small_file_with_advanced_features(self, file_path, page=0, page_size=1000, search_params=None):
        """
        Parse a small CSV/TXT file with advanced features like searching and filtering
        
        For files that can be loaded completely into memory
        """
        logger.info(f"Verwerken van klein bestand: {file_path}")
        
        # List of encodings to try, in order
        encodings_to_try = ['utf-8', 'latin-1', 'windows-1252', 'iso-8859-1']
        
        for encoding in encodings_to_try:
            try:
                # Try to parse with pandas for better performance on smaller files
                df = pd.read_csv(file_path, encoding=encoding)
                logger.info(f"Successfully parsed file using {encoding} encoding")
                
                # Apply filtering if specified
                df = self._apply_filters_to_dataframe(df, search_params)
                
                # Get total record count after filtering
                total_records = len(df)
                total_pages = (total_records + page_size - 1) // page_size if page_size > 0 else 1
                
                # Apply pagination
                start_idx = page * page_size
                end_idx = min(start_idx + page_size, total_records)
                
                # Slice the dataframe
                df_page = df.iloc[start_idx:end_idx]
                
                # Convert to list of dictionaries
                data = json.loads(df_page.to_json(orient='records'))
                
                # Return paginated response with metadata
                return {
                    "data": data,
                    "pagination": {
                        "page": page,
                        "pageSize": page_size,
                        "totalRecords": total_records,
                        "totalPages": total_pages,
                        "hasNextPage": page < total_pages - 1,
                        "hasPrevPage": page > 0
                    }
                }
                
            except UnicodeDecodeError:
                # Try the next encoding
                logger.warning(f"Failed to parse file with {encoding}, trying next encoding")
                continue
            except Exception as e:
                logger.error(f"Fout bij parsen van bestand met pandas met {encoding} encoding: {str(e)}")
                # For non-encoding errors, continue to fallback method
                break
        
        # Fall back to CSV reader if pandas fails with all encodings
        for encoding in encodings_to_try:
            try:
                # Read the entire file
                data = []
                with open(file_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    field_names = reader.fieldnames
                    
                    for row in reader:
                        data.append(dict(row))
                
                logger.info(f"Successfully parsed file using fallback CSV reader with {encoding} encoding")
                
                # Apply filtering
                filtered_data = self._apply_filters_to_list(data, search_params)
                
                # Apply sorting if specified
                sorted_data = self._apply_sorting_to_list(filtered_data, search_params)
                
                # Get total record count after filtering
                total_records = len(sorted_data)
                total_pages = (total_records + page_size - 1) // page_size if page_size > 0 else 1
                
                # Apply pagination
                start_idx = page * page_size
                end_idx = min(start_idx + page_size, total_records)
                
                # Return paginated response with metadata
                return {
                    "data": sorted_data[start_idx:end_idx],
                    "pagination": {
                        "page": page,
                        "pageSize": page_size,
                        "totalRecords": total_records,
                        "totalPages": total_pages,
                        "hasNextPage": page < total_pages - 1,
                        "hasPrevPage": page > 0
                    }
                }
            
            except UnicodeDecodeError:
                # Try the next encoding
                logger.warning(f"Fallback CSV parsing failed with {encoding}, trying next encoding")
                continue
            except Exception as e:
                logger.error(f"Fall-back CSV parsing mislukt met {encoding}: {str(e)}")
                continue
        
        # If all methods fail, return error
        logger.error(f"Failed to parse file with all encoding methods")
        return None
    
    def _parse_large_file_with_advanced_features(self, file_path, page=0, page_size=1000, search_params=None):
        """
        Parse a large CSV/TXT file with advanced features while optimizing memory usage
        
        For files too large to load completely into memory
        """
        logger.info(f"Verwerken van groot bestand met optimalisatie: {file_path}")
        
        try:
            # Determine if we need to process the entire file or can optimize with direct pagination
            has_filters = (search_params['search']['query'] is not None or 
                         len(search_params['filters']) > 0 or 
                         search_params['sort']['field'] is not None)
            
            if has_filters:
                logger.info(f"Filters of sortering gedetecteerd, volledige bestandsverwerking nodig")
                return self._parse_large_file_with_full_processing(file_path, page, page_size, search_params)
            else:
                logger.info(f"Geen filters, efficiënte paginering wordt toegepast")
                return self._parse_large_file_with_efficient_direct_pagination(file_path, page, page_size)
                
        except Exception as e:
            logger.error(f"Fout bij verwerken van groot bestand: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def _parse_large_file_with_full_processing(self, file_path, page=0, page_size=1000, search_params=None):
        """
        Parse a large file with complete processing for filtering, searching, and sorting
        
        Uses a more memory-efficient streaming approach
        """
        logger.info(f"Volledige verwerking voor bestand: {file_path}")
        
        # Use our new optimized streaming method for better memory efficiency
        return self._parse_large_file_with_streaming_filters(file_path, page, page_size, search_params)
    
    def _parse_large_file_with_efficient_direct_pagination(self, file_path, page=0, page_size=1000):
        """
        Parse a large file with optimized direct pagination using memory-mapped file access
        
        Highly memory-efficient approach for large files like stop_times.txt without filtering
        """
        logger.info(f"Optimale memory-mapped paginering: pagina {page}, grootte {page_size} voor bestand {file_path}")
        
        # List of encodings to try, in order
        encodings_to_try = ['utf-8', 'latin-1', 'windows-1252', 'iso-8859-1']
        
        for encoding in encodings_to_try:
            try:
                # Count total lines with optimized method
                with open(file_path, 'rb') as f:
                    # Use mmap for more efficient line counting
                    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                    total_lines = 0
                    for _ in iter(mm.readline, b''):
                        total_lines += 1
                    mm.close()
                
                # Adjust for header
                total_lines -= 1
                total_pages = (total_lines + page_size - 1) // page_size  # Ceiling division
                
                logger.info(f"Bestand heeft {total_lines} regels, {total_pages} pagina's")
                
                # Read the header only - more efficient
                with open(file_path, 'r', encoding=encoding) as f:
                    header = f.readline().strip().split(',')
                
                # Skip to the correct page and read only needed lines
                start_line = page * page_size + 1  # +1 for header
                end_line = start_line + page_size
                
                # Limit to actual file size
                end_line = min(end_line, total_lines + 1)  # +1 because file lines are 1-indexed
                
                logger.info(f"Memory-efficiënt lezen van regels {start_line} tot {end_line} met {encoding} encoding")
                
                # Read the data more efficiently
                data = []
                
                with open(file_path, 'r', encoding=encoding) as f:
                    # Skip header line
                    next(f)
                    
                    # Using file seek to jump ahead if possible
                    if start_line > 100:  # Only worth doing for larger offsets
                        # Read in chunks to find the right position
                        chunk_size = 100000
                        current_pos = f.tell()
                        chunk = f.read(chunk_size)
                        newlines_count = 0
                        
                        # Count newlines and advance position until we're close to our target
                        while newlines_count < start_line - 1 and chunk:
                            newlines_in_chunk = chunk.count('\n')
                            if newlines_count + newlines_in_chunk >= start_line - 1:
                                # We're close enough, read line by line from here
                                excess = newlines_count + newlines_in_chunk - (start_line - 1)
                                f.seek(current_pos + chunk.rfind('\n', 0, len(chunk) - excess) + 1)
                                for _ in range(excess):
                                    next(f, None)
                                newlines_count = start_line - 1
                                break
                            
                            newlines_count += newlines_in_chunk
                            current_pos = f.tell()
                            chunk = f.read(chunk_size)
                            
                        # If we didn't find enough newlines, reset and do it the slow way
                        if newlines_count < start_line - 1:
                            f.seek(0)
                            next(f)  # Skip header
                            for _ in range(start_line - 1):
                                next(f, None)
                    else:
                        # For small offsets, just read line by line
                        for _ in range(start_line - 1):
                            next(f, None)
                    
                    # Read required lines and convert to dictionaries
                    for i in range(end_line - start_line):
                        line = next(f, None)
                        if line is None:
                            break
                        
                        # Process line into dict
                        row = dict(zip(header, line.strip().split(',')))
                        data.append(row)
                
                # Force garbage collection to free memory
                gc.collect()
                
                logger.info(f"Successfully parsed large file using {encoding} encoding")
                
                # Return paginated response with metadata
                return {
                    "data": data,
                    "pagination": {
                        "page": page,
                        "pageSize": page_size,
                        "totalRecords": total_lines,
                        "totalPages": total_pages,
                        "hasNextPage": page < total_pages - 1,
                        "hasPrevPage": page > 0
                    }
                }
                
            except UnicodeDecodeError:
                # Try the next encoding
                logger.warning(f"Failed to parse large file with {encoding}, trying next encoding")
                continue
            except Exception as e:
                logger.error(f"Fout bij optimale paginering van bestand met {encoding} encoding: {str(e)}")
                logger.error(traceback.format_exc())
                continue
        
        # If all methods fail, return error
        logger.error(f"Failed to parse large file with all encoding methods")
        return None
    
    def _parse_large_file_with_streaming_filters(self, file_path, page=0, page_size=1000, search_params=None):
        """
        Parse a large file with streaming filter processing to avoid loading entire file
        
        Memory-efficient for large files when filtering is needed
        """
        logger.info(f"Streaming verwerking met filters voor bestand: {file_path}")
        
        # List of encodings to try, in order
        encodings_to_try = ['utf-8', 'latin-1', 'windows-1252', 'iso-8859-1']
        
        for encoding in encodings_to_try:
            try:
                # Read the header
                with open(file_path, 'r', encoding=encoding) as f:
                    header = f.readline().strip().split(',')
                
                # Determine if we're filtering on stop_id or trip_id, which are common in stop_times.txt
                key_filters = {}
                for field, value in search_params['filters'].items():
                    if field in ['stop_id', 'trip_id', 'route_id']:
                        key_filters[field] = str(value)
                
                # If we have key filters, we can be more efficient by reading only chunks
                # that might contain matching records
                if key_filters:
                    logger.info(f"Efficiënte filtering op sleutelvelden: {key_filters}")
                    result = self._parse_with_key_filters(file_path, header, page, page_size, search_params, key_filters)
                    if result:
                        return result
                    else:
                        # If key filters failed, continue with regular streaming 
                        logger.warning(f"Key filter method failed, falling back to normal streaming")
                
                # Otherwise, process with streaming but need to check every row
                filtered_count = 0
                filtered_data = []
                
                # First pass: count matching records to determine total pages
                with open(file_path, 'r', encoding=encoding) as f:
                    next(f)  # Skip header
                    
                    for line in f:
                        row = dict(zip(header, line.strip().split(',')))
                        
                        # Check if this row matches filters
                        if self._row_matches_filters(row, search_params):
                            filtered_count += 1
                
                # Calculate pagination info
                total_records = filtered_count
                total_pages = (total_records + page_size - 1) // page_size if page_size > 0 else 1
                
                # If requested page exceeds total pages, return empty result
                if page >= total_pages and total_pages > 0:
                    return {
                        "data": [],
                        "pagination": {
                            "page": page,
                            "pageSize": page_size,
                            "totalRecords": total_records,
                            "totalPages": total_pages,
                            "hasNextPage": False,
                            "hasPrevPage": page > 0
                        }
                    }
                
                # Second pass: collect just the records for the requested page
                with open(file_path, 'r', encoding=encoding) as f:
                    next(f)  # Skip header
                    
                    current_filtered_idx = 0
                    start_idx = page * page_size
                    end_idx = start_idx + page_size
                    
                    for line in f:
                        row = dict(zip(header, line.strip().split(',')))
                        
                        # Check if this row matches filters
                        if self._row_matches_filters(row, search_params):
                            if start_idx <= current_filtered_idx < end_idx:
                                filtered_data.append(row)
                            elif current_filtered_idx >= end_idx:
                                break  # We've gone past what we need
                            
                            current_filtered_idx += 1
                
                # Apply sorting if needed - only to the page we're returning
                if search_params['sort']['field']:
                    filtered_data = self._apply_sorting_to_list(filtered_data, search_params)
                
                # Force garbage collection
                gc.collect()
                
                logger.info(f"Successfully parsed file with streaming filters using {encoding} encoding")
                
                # Return the paginated results
                return {
                    "data": filtered_data,
                    "pagination": {
                        "page": page,
                        "pageSize": page_size,
                        "totalRecords": total_records,
                        "totalPages": total_pages,
                        "hasNextPage": page < total_pages - 1,
                        "hasPrevPage": page > 0
                    }
                }
                
            except UnicodeDecodeError:
                # Try the next encoding
                logger.warning(f"Failed to parse file with streaming filters using {encoding}, trying next encoding")
                continue
            except Exception as e:
                logger.error(f"Fout bij streaming verwerking van bestand met {encoding} encoding: {str(e)}")
                logger.error(traceback.format_exc())
                continue
        
        # If all methods fail, return error
        logger.error(f"Failed to parse file with streaming filters using all encodings")
        return None
    
    def _parse_with_key_filters(self, file_path, header, page, page_size, search_params, key_filters):
        """
        Parse a file with key-based filtering (optimized for stop_id, trip_id, etc.)
        """
        logger.info(f"Sleutel-gebaseerde filtering op: {list(key_filters.keys())}")
        
        try:
            filtered_data = []
            buffer_size = min(page_size * 5, 10000)  # Reasonable buffer size
            
            # First pass for counting only
            record_count = 0
            with open(file_path, 'r', encoding='utf-8') as f:
                next(f)  # Skip header
                
                for line in f:
                    row_data = line.strip().split(',')
                    matches_key = False
                    
                    # Quick check on raw data without converting to dict yet
                    for field, value in key_filters.items():
                        field_idx = header.index(field) if field in header else -1
                        if field_idx >= 0 and field_idx < len(row_data) and row_data[field_idx] == value:
                            matches_key = True
                            break
                    
                    # If matches key filter, check full filters
                    if matches_key:
                        row = dict(zip(header, row_data))
                        if self._row_matches_filters(row, search_params):
                            record_count += 1
            
            # Calculate pagination
            total_records = record_count
            total_pages = (total_records + page_size - 1) // page_size if page_size > 0 else 1
            
            # Get just the records for current page
            start_idx = page * page_size
            end_idx = start_idx + page_size
            
            if total_records > 0:
                # Second pass to get the needed records
                with open(file_path, 'r', encoding='utf-8') as f:
                    next(f)  # Skip header
                    
                    current_idx = 0
                    for line in f:
                        row_data = line.strip().split(',')
                        matches_key = False
                        
                        # Quick check on raw data
                        for field, value in key_filters.items():
                            field_idx = header.index(field) if field in header else -1
                            if field_idx >= 0 and field_idx < len(row_data) and row_data[field_idx] == value:
                                matches_key = True
                                break
                        
                        # If matches key filter, check full filters
                        if matches_key:
                            row = dict(zip(header, row_data))
                            if self._row_matches_filters(row, search_params):
                                if start_idx <= current_idx < end_idx:
                                    filtered_data.append(row)
                                elif current_idx >= end_idx:
                                    break  # We've gone past what we need
                                
                                current_idx += 1
            
            # Apply sorting if needed - only to the page we're returning
            if search_params['sort']['field']:
                filtered_data = self._apply_sorting_to_list(filtered_data, search_params)
            
            # Force garbage collection
            gc.collect()
            
            # Return the paginated results
            return {
                "data": filtered_data,
                "pagination": {
                    "page": page,
                    "pageSize": page_size,
                    "totalRecords": total_records,
                    "totalPages": total_pages,
                    "hasNextPage": page < total_pages - 1,
                    "hasPrevPage": page > 0
                }
            }
            
        except Exception as e:
            logger.error(f"Fout bij sleutel-gebaseerde filtering: {str(e)}")
            logger.error(traceback.format_exc())
            return None
            
    def _row_matches_filters(self, row, search_params):
        """
        Check if a row matches the filter criteria
        Used for streaming filtering
        """
        # Check search query
        if search_params['search']['query']:
            query = search_params['search']['query'].lower()
            field = search_params['search']['field']
            
            if field:
                if field not in row or str(row[field]).lower().find(query) < 0:
                    return False
            else:
                found = False
                for key, value in row.items():
                    if str(value).lower().find(query) >= 0:
                        found = True
                        break
                if not found:
                    return False
        
        # Check specific filters
        for field, value in search_params['filters'].items():
            if field not in row or str(row[field]) != str(value):
                return False
        
        return True
    
    def _apply_filters_to_dataframe(self, df, search_params):
        """Apply filters to a pandas DataFrame"""
        if not search_params:
            return df
        
        # Copy the dataframe to avoid modifying the original
        filtered_df = df.copy()
        
        # Apply search query if specified
        if search_params['search']['query']:
            query = search_params['search']['query']
            field = search_params['search']['field']
            
            # If field is specified, search only in that column
            if field and field in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[field].astype(str).str.contains(query, case=False, na=False)]
            # Otherwise search in all string columns
            else:
                mask = False
                for col in filtered_df.select_dtypes(include=['object']).columns:
                    mask = mask | filtered_df[col].astype(str).str.contains(query, case=False, na=False)
                filtered_df = filtered_df[mask]
        
        # Apply specific filters
        for field, value in search_params['filters'].items():
            if field in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[field].astype(str) == str(value)]
        
        # Apply sorting
        if search_params['sort']['field'] and search_params['sort']['field'] in filtered_df.columns:
            ascending = search_params['sort']['direction'].lower() != 'desc'
            filtered_df = filtered_df.sort_values(by=search_params['sort']['field'], ascending=ascending)
        
        return filtered_df
    
    def _apply_filters_to_list(self, data_list, search_params):
        """Apply filters to a list of dictionaries"""
        if not search_params:
            return data_list
        
        filtered_list = data_list
        
        # Apply search query if specified
        if search_params['search']['query']:
            query = search_params['search']['query'].lower()
            field = search_params['search']['field']
            
            # If field is specified, search only in that field
            if field:
                filtered_list = [
                    item for item in filtered_list 
                    if field in item and 
                    str(item[field]).lower().find(query) >= 0
                ]
            # Otherwise search in all fields
            else:
                filtered_list = [
                    item for item in filtered_list 
                    if any(
                        str(value).lower().find(query) >= 0 
                        for key, value in item.items()
                    )
                ]
        
        # Apply specific filters
        for field, value in search_params['filters'].items():
            filtered_list = [
                item for item in filtered_list 
                if field in item and str(item[field]) == str(value)
            ]
        
        return filtered_list
    
    def _apply_sorting_to_list(self, data_list, search_params):
        """Apply sorting to a list of dictionaries"""
        if not search_params or not search_params['sort']['field']:
            return data_list
        
        sort_field = search_params['sort']['field']
        reverse = search_params['sort']['direction'].lower() == 'desc'
        
        # Sort the data
        # Use a key function that handles missing fields and converts to string
        return sorted(
            data_list,
            key=lambda x: str(x.get(sort_field, '')).lower(),
            reverse=reverse
        )
        
    def _parse_csv_file(self, file_path):
        """Parse a CSV file and return as JSON"""
        try:
            df = pd.read_csv(file_path)
            return json.loads(df.to_json(orient='records'))
        except Exception as e:
            logger.error(f"Fout bij parsen van CSV bestand {file_path}: {str(e)}")
            
            # Try alternative parsing if pandas fails
            try:
                result = []
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        result.append(dict(row))
                return result
            except Exception as e2:
                logger.error(f"Alternatieve CSV parsing mislukt: {str(e2)}")
                return None
    
    def _parse_txt_file(self, file_path):
        """Parse a GTFS TXT file and return as JSON"""
        try:
            # Try to parse as a CSV (GTFS txt files are typically comma-separated)
            df = pd.read_csv(file_path)
            return json.loads(df.to_json(orient='records'))
        except Exception as e:
            logger.error(f"Fout bij parsen van TXT bestand {file_path}: {str(e)}")
            
            # Try alternative parsing if pandas fails
            try:
                result = []
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        result.append(dict(row))
                return result
            except Exception as e2:
                logger.error(f"Alternatieve TXT parsing mislukt: {str(e2)}")
                
                # Fall back to plain text
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return f.read()
                except:
                    return None

    def _parse_large_file_with_direct_pagination(self, file_path, page=0, page_size=1000):
        """
        [DEPRECATED] Use _parse_large_file_with_efficient_direct_pagination instead
        Parse a large file with direct pagination (no filtering)
        """
        # Redirect to our more memory-efficient implementation
        return self._parse_large_file_with_efficient_direct_pagination(file_path, page, page_size)
