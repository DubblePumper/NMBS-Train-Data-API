"""
JSON Schema validatie voor API verzoeken
"""
from jsonschema import validate, ValidationError
from flask import request, jsonify
import functools
import logging

logger = logging.getLogger(__name__)

# Schema definities voor verschillende API endpoints
UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "force": {"type": "boolean"},
        "update_type": {"type": "string", "enum": ["realtime", "planning", "netex", "all"]},
        "clear_cache": {"type": "boolean"}
    },
    "required": ["force"]
}

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "search": {"type": "string"},
        "field": {"type": "string"},
        "exact": {"type": "boolean"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 5000},
        "page": {"type": "integer", "minimum": 0},
        "sort_by": {"type": "string"},
        "sort_direction": {"type": "string", "enum": ["asc", "desc"]}
    }
}

# Schema map voor verschillende endpoints
SCHEMAS = {
    "update": UPDATE_SCHEMA,
    "search": SEARCH_SCHEMA
}

def validate_json(schema_name):
    """
    Decorator voor JSON schema validatie in Flask routes
    
    Args:
        schema_name: De naam van het schema om te valideren tegen
        
    Returns:
        De gedecoreerde functie
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            # Controleer of er JSON data is
            if not request.is_json:
                logger.warning(f"Verzoek naar {request.path} bevat geen JSON data")
                return jsonify({"error": "Verzoek moet JSON data bevatten"}), 400
            
            # Haal het schema op
            schema = SCHEMAS.get(schema_name)
            if not schema:
                logger.error(f"Onbekend schema: {schema_name}")
                return f(*args, **kwargs)
            
            # Valideer de JSON data
            try:
                validate(instance=request.json, schema=schema)
            except ValidationError as e:
                logger.warning(f"JSON validatie fout: {e}")
                return jsonify({
                    "error": "Ongeldige JSON data", 
                    "details": str(e),
                    "path": list(e.path) if e.path else None
                }), 400
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_params(schema_name):
    """
    Decorator voor query parameter validatie in Flask routes
    
    Args:
        schema_name: De naam van het schema om te valideren tegen
        
    Returns:
        De gedecoreerde functie
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            # Haal het schema op
            schema = SCHEMAS.get(schema_name)
            if not schema:
                logger.error(f"Onbekend schema: {schema_name}")
                return f(*args, **kwargs)
            
            # Converteer query parameters
            query_params = {}
            for key, value in request.args.items():
                # Probeer boolean te converteren
                if value.lower() in ('true', 'false'):
                    query_params[key] = (value.lower() == 'true')
                # Probeer integer te converteren
                elif value.isdigit():
                    query_params[key] = int(value)
                else:
                    query_params[key] = value
            
            # Valideer de parameters
            try:
                validate(instance=query_params, schema=schema)
            except ValidationError as e:
                logger.warning(f"Parameter validatie fout: {e}")
                return jsonify({
                    "error": "Ongeldige parameters", 
                    "details": str(e),
                    "path": list(e.path) if e.path else None
                }), 400
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
