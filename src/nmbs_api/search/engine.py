from typing import Dict, List, Any, Union

from rapidfuzz import fuzz


class SearchEngine:
    """Search engine for NMBS API data with exact, partial, and fuzzy matching."""

    def __init__(self):
        self.indices = {}
        self.search_cache = {}

    def build_index(self, data: List[Dict], field: str) -> Dict:
        """Build a simple value-to-row-index map for fast exact lookups."""
        index = {}
        for i, item in enumerate(data):
            if field in item:
                value = str(item[field])
                if value not in index:
                    index[value] = []
                index[value].append(i)
        return index

    def search_exact(self, data: List[Dict], field: str, value: str) -> List[Dict]:
        """Perform exact search in one field."""
        index_key = f"{id(data)}:{field}"
        if index_key not in self.indices:
            self.indices[index_key] = self.build_index(data, field)

        index = self.indices[index_key]
        value_str = str(value)

        if value_str in index:
            return [data[i] for i in index[value_str]]
        return []

    def search_partial(self, data: List[Dict], field: str, value: str) -> List[Dict]:
        """Perform substring search in one field."""
        results = []
        value_lower = str(value).lower()

        for item in data:
            if field in item and item[field] is not None:
                item_value = str(item[field]).lower()
                if value_lower in item_value:
                    results.append(item)

        return results

    def search_fuzzy(self, data: List[Dict], field: str, value: str, threshold: int = 75) -> List[Dict]:
        """Perform fuzzy matching in one field."""
        results = []
        value_str = str(value)

        for item in data:
            if field in item and item[field] is not None:
                item_value = str(item[field])
                score = fuzz.partial_ratio(value_str.lower(), item_value.lower())
                if score >= threshold:
                    item['_score'] = score
                    results.append(item)

        return sorted(results, key=lambda x: x.get('_score', 0), reverse=True)

    def search_realtime_data(
        self,
        data: Dict,
        search_field: str,
        search_value: str,
        exact: bool = False,
    ) -> Dict:
        """Search in GTFS real-time payloads."""
        result = {
            "header": data.get("header", {}),
            "entity": [],
        }

        entities = data.get("entity", [])

        if search_field == "timestamp" and search_field in data.get("header", {}):
            header_timestamp = str(data["header"]["timestamp"])
            if (exact and header_timestamp == search_value) or (not exact and search_value in header_timestamp):
                return data

        if search_field == "id":
            for entity in entities:
                entity_id = entity.get("id", "")
                if (exact and entity_id == search_value) or (not exact and search_value in entity_id):
                    result["entity"].append(entity)
            return result

        if search_field == "stopId":
            for entity in entities:
                if "tripUpdate" in entity and "stopTimeUpdate" in entity["tripUpdate"]:
                    match_found = False
                    for update in entity["tripUpdate"]["stopTimeUpdate"]:
                        stop_id = update.get("stopId", "")
                        if (exact and stop_id == search_value) or (not exact and search_value in stop_id):
                            match_found = True
                            break

                    if match_found:
                        result["entity"].append(entity)
            return result

        return data

    def search_planning_data(
        self,
        data: List[Dict],
        search_field: str,
        search_value: str,
        exact: bool = False,
    ) -> List[Dict]:
        """Search in static/planning data rows."""
        cache_key = f"{id(data)}:{search_field}:{search_value}:{exact}"
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]

        if exact:
            results = self.search_exact(data, search_field, search_value)
        elif search_field in ['stop_name', 'route_long_name', 'trip_headsign', 'translation']:
            results = self.search_fuzzy(data, search_field, search_value)
        else:
            results = self.search_partial(data, search_field, search_value)

        self.search_cache[cache_key] = results
        return results

    def execute_search(
        self,
        data: Union[Dict, List[Dict]],
        search_field: str,
        search_value: str,
        data_type: str = 'planning',
        exact: bool = False,
        limit: int = 1000,
    ) -> Union[Dict, List[Dict]]:
        """Execute search by payload type."""
        if data_type == 'realtime':
            results = self.search_realtime_data(data, search_field, search_value, exact)
        else:
            results = self.search_planning_data(data, search_field, search_value, exact)
            if isinstance(results, list) and len(results) > limit:
                results = results[:limit]

        return results

    def clear_cache(self):
        """Clear in-memory search caches."""
        self.search_cache = {}
        self.indices = {}


search_engine = SearchEngine()


def search_data(data, search_params, data_type='planning', limit=1000):
    """Search helper compatible with existing code usage."""
    search_field = search_params.get('search')
    if not search_field:
        return data

    search_value = search_params.get(search_field)
    if not search_value:
        return data

    exact = str(search_params.get('exact', '')).lower() == 'true'

    return search_engine.execute_search(
        data=data,
        search_field=search_field,
        search_value=search_value,
        data_type=data_type,
        exact=exact,
        limit=int(search_params.get('limit', limit)),
    )


def optimize_data_for_search(data, fields=None):
    """Pre-build search indices for selected fields."""
    if not isinstance(data, list) or not data:
        return

    if fields is None and data:
        fields = data[0].keys()

    for field in fields:
        search_engine.build_index(data, field)
