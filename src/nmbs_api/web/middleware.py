"""
Middleware components for the NMBS Train Data API
"""
import logging
from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logger = logging.getLogger(__name__)

# List of allowed domains - now allowing all hosts
# ALLOWED_DOMAINS = ['nmbsapi.sanderzijntestjes.be', 'localhost', '127.0.0.1']

def setup_middleware(app, cors_origins='*'):
    """
    Set up all middleware for the Flask app
    
    Args:
        app (Flask): The Flask application instance
        cors_origins (str): Comma-separated list of allowed origins or '*'
    """
    # Add CORS support (configurable via CORS_ORIGINS env var)
    if isinstance(cors_origins, str):
        stripped = cors_origins.strip()
        origins = '*' if stripped == '*' else [o.strip() for o in stripped.split(',') if o.strip()]
    else:
        origins = cors_origins

    CORS(
        app,
        resources={
            r"/*": {
                "origins": origins,
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "X-API-Token"]
            }
        }
    )
    logger.info(f"CORS configured for origins: {origins}")
    
    # Add support for proxy headers
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Domain validation disabled - allow all hosts to access the API
    # @app.before_request
    # def validate_domain():
    #     """Ensure that the API is only accessed through the proper domain name"""
    #     host = request.host.split(':')[0]  # Remove port if present
    #     
    #     # Log the host for debugging
    #     logger.debug(f"Request received from host: {host}")
    #     
    #     # Allow access if the host is in the allowed domains
    #     if host in ALLOWED_DOMAINS:
    #         return None
    #     
    #     # For direct IP access, block it
    #     logger.warning(f"Unauthorized access attempt from host: {host}")
    #     return jsonify({
    #         "error": "Access denied",
    #         "message": "This API is only accessible via https://nmbsapi.sanderzijntestjes.be/",
    #         "redirect": "https://nmbsapi.sanderzijntestjes.be/"
    #     }), 403  # Forbidden