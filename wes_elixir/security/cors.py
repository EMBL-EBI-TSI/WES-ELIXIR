import logging

from flask_cors import CORS


# Get logger instance
logger = logging.getLogger(__name__)


def enable_cors(app):
    '''Enable cross- resources sharing for Connexion app'''

    # Enable CORS
    CORS(app)
    logger.info("Enabled CORS for Connexion app.")