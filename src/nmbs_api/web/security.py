"""
Security features for the NMBS Train Data API
- Rate limiting to prevent abuse
- Input validation and sanitization
- Security headers for HTTP responses
- HTTPS enforcement
- Security audit functionality
"""
import os
import re
import json
import logging
import datetime
import functools
import ipaddress
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union

from flask import Flask, request, Response, g, abort, redirect, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException

# Configure logging
logger = logging.getLogger(__name__)

# --- Rate Limiting Configuration ---
DEFAULT_RATE_LIMITS = {
    "default": ["200 per day", "50 per hour"],
    "health_check": "60 per minute",
    "trip_search": "30 per minute",
    "station_info": "60 per minute",
}

# --- Security Configuration ---
SECURITY_HEADERS = {
    'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline';",
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
    'Pragma': 'no-cache',
    'Referrer-Policy': 'strict-origin-when-cross-origin'
}

# List of known safe domains for hostname validation
SAFE_DOMAINS = [
    'localhost',
    '127.0.0.1',
    'nmbsapi.sanderzijntestjes.be',
]

# --- Input Validation ---
VALIDATION_PATTERNS = {
    'station_id': re.compile(r'^[A-Z0-9]{1,10}$'),
    'train_id': re.compile(r'^[A-Za-z0-9]{1,10}$'),
    'page': re.compile(r'^\d+$'),
    'page_size': re.compile(r'^\d+$'),
    'date': re.compile(r'^\d{4}-\d{2}-\d{2}$'),
    'time': re.compile(r'^\d{2}:\d{2}(:\d{2})?$'),
}

# --- Audit Configuration ---
AUDIT_LOG_DIR = 'logs/security'

# --- Rate Limiter Setup ---
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=DEFAULT_RATE_LIMITS["default"],
    storage_uri="memory://",
)

def setup_security(app: Flask) -> None:
    """
    Set up all security features for the Flask app
    
    Args:
        app (Flask): The Flask application instance
    """
    # Initialize rate limiter
    limiter.init_app(app)
    
    # Create audit log directory
    os.makedirs(AUDIT_LOG_DIR, exist_ok=True)
    
    # Configure app
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    
    # Register security middleware
    _register_security_middleware(app)
    
    logger.info("Security features initialized")

def _register_security_middleware(app: Flask) -> None:
    """Register all security middleware with the Flask app"""
    
    # HTTPS enforcement disabled to allow all types of connections
    # @app.before_request
    # def enforce_https():
    #     """Ensure all requests use HTTPS"""
    #     # Skip for development environments
    #     if request.host.startswith(('localhost', '127.0.0.1')):
    #         return None
    #         
    #     # Check if request is already secure
    #     if not request.is_secure:
    #         url = request.url.replace('http://', 'https://', 1)
    #         return redirect(url, code=301)  # Permanent redirect
    
    @app.before_request
    def validate_input():
        """Validate and sanitize request parameters"""
        # Store original parameters for logging purposes
        g.original_params = dict(request.args)
        g.sanitized = False
        
        # Check all request parameters
        sanitized_args = {}
        has_validation_error = False
        validation_errors = []
        
        for param_name, param_value in request.args.items():
            # Skip empty parameters
            if not param_value:
                continue
                
            # Apply pattern validation if applicable
            if param_name in VALIDATION_PATTERNS:
                if not VALIDATION_PATTERNS[param_name].match(str(param_value)):
                    has_validation_error = True
                    validation_errors.append({
                        'param': param_name,
                        'value': param_value,
                        'reason': 'Invalid format'
                    })
                    continue
            
            # Additional parameter-specific validation
            if param_name == 'page' or param_name == 'page_size':
                try:
                    value = int(param_value)
                    if value < 0 or (param_name == 'page_size' and value > 1000):
                        has_validation_error = True
                        validation_errors.append({
                            'param': param_name,
                            'value': param_value,
                            'reason': 'Value out of allowed range'
                        })
                        continue
                    sanitized_args[param_name] = value
                except ValueError:
                    has_validation_error = True
                    validation_errors.append({
                        'param': param_name,
                        'value': param_value,
                        'reason': 'Not a valid number'
                    })
                    continue
            else:
                # Basic sanitization for string parameters
                sanitized_value = str(param_value).strip()
                # Remove control characters and ensure we're dealing with valid strings
                sanitized_value = ''.join(c for c in sanitized_value if c.isprintable())
                sanitized_args[param_name] = sanitized_value
        
        # Store sanitized parameters
        g.sanitized_params = sanitized_args
        g.sanitized = True
        
        # If validation failed, log and abort
        if has_validation_error:
            log_security_event('input_validation_failure', {
                'errors': validation_errors,
                'path': request.path
            })
            abort(400, description="Invalid request parameters")
    
    @app.after_request
    def add_security_headers(response: Response) -> Response:
        """Add security headers to all responses"""
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
            
        return response
    
    @app.after_request
    def log_request(response: Response) -> Response:
        """Log API requests for auditing purposes"""
        # Don't log health checks to reduce noise
        if request.path == '/api/health':
            return response
            
        # Basic request info
        log_data = {
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'method': request.method,
            'path': request.path,
            'remote_addr': request.remote_addr,
            'user_agent': request.user_agent.string,
            'status_code': response.status_code
        }
        
        # Add request parameters if available
        if hasattr(g, 'original_params'):
            log_data['parameters'] = g.original_params
            
        # Log to audit file
        log_security_event('api_request', log_data)
        
        return response
    
    @app.errorhandler(429)
    def handle_rate_limit_error(error):
        """Custom handler for rate limit errors"""
        log_security_event('rate_limit_exceeded', {
            'remote_addr': request.remote_addr,
            'path': request.path,
            'user_agent': request.user_agent.string
        })
        
        return {
            'error': 'Too many requests',
            'message': 'You have exceeded the rate limit. Please try again later.'
        }, 429

def log_security_event(event_type: str, data: dict) -> None:
    """
    Log a security event to the audit log
    
    Args:
        event_type: Type of security event
        data: Event details
    """
    try:
        # Create dated log file
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(AUDIT_LOG_DIR, f'security-audit-{today}.log')
        
        # Prepare log entry
        entry = {
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'event_type': event_type,
            'data': data
        }
        
        # Write to log file
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
            
    except Exception as e:
        logger.error(f"Failed to log security event: {str(e)}")

def validate_param(param: str, pattern_name: str) -> bool:
    """
    Validate a parameter against a named validation pattern
    
    Args:
        param: Parameter value to validate
        pattern_name: Name of the pattern to check against
    
    Returns:
        bool: True if parameter is valid, False otherwise
    """
    if pattern_name not in VALIDATION_PATTERNS:
        return False
    return bool(VALIDATION_PATTERNS[pattern_name].match(param))

def sanitize_param(param: str) -> str:
    """
    Sanitize a user input parameter
    
    Args:
        param: Parameter to sanitize
    
    Returns:
        str: Sanitized parameter
    """
    if not param:
        return ""
        
    # Convert to string and strip whitespace
    result = str(param).strip()
    
    # Remove control characters and non-printables
    result = ''.join(c for c in result if c.isprintable())
    
    return result

def get_sanitized_args() -> Dict[str, Any]:
    """
    Get sanitized request arguments if available
    
    Returns:
        Dict: The sanitized arguments or original args if sanitization hasn't run
    """
    if hasattr(g, 'sanitized') and g.sanitized:
        return g.sanitized_params
    return dict(request.args)

def run_security_audit() -> Dict[str, Any]:
    """
    Run a basic security audit and return results
    
    Returns:
        dict: Audit results
    """
    results = {
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'checks': []
    }
    
    # Check rate limiting configuration
    results['checks'].append({
        'name': 'rate_limiting',
        'status': 'enabled' if limiter.enabled else 'disabled',
        'details': DEFAULT_RATE_LIMITS
    })
    
    # Check HTTPS enforcement
    results['checks'].append({
        'name': 'https_enforcement',
        'status': 'disabled',
        'details': 'HTTPS redirect middleware is currently disabled in _register_security_middleware',
        'except': ['localhost', '127.0.0.1']
    })
    
    # Check security headers
    results['checks'].append({
        'name': 'security_headers',
        'status': 'enabled',
        'headers': list(SECURITY_HEADERS.keys())
    })
    
    # Check input validation
    results['checks'].append({
        'name': 'input_validation',
        'status': 'enabled',
        'patterns': list(VALIDATION_PATTERNS.keys())
    })
    
    # Check logging
    log_dir = Path(AUDIT_LOG_DIR)
    log_files = list(log_dir.glob('security-audit-*.log'))
    results['checks'].append({
        'name': 'security_logging',
        'status': 'enabled' if log_files else 'warning',
        'details': {
            'log_dir': AUDIT_LOG_DIR,
            'log_files': len(log_files),
        }
    })
    
    return results