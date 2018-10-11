import logging
from logging.config import dictConfig
import os

from wes_elixir.config.config_parser import YAMLConfigParser


# Get logger instance
logger = logging.getLogger(__name__)


def configure_logging(
    config_var=None,
    default_path=os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'log_config.yaml')),
    fallback_level=logging.DEBUG
):

    '''Configure base logger'''

    # Create parser instance
    config = YAMLConfigParser()

    # Parse config
    try:
        paths = config.update_from_yaml(
            config_paths=[default_path],
            config_vars=[config_var],
        )
        dictConfig(config)

    # Fall back to default if no log config file was found/accessible 
    except (FileNotFoundError, PermissionError):
        logger.warning("No custom logging config found. Falling back to default config.")
        logging.basicConfig(level=fallback_level)
    
    # Log info 
    else:
        logger.info("Logging config loaded from '{paths}'.".format(paths=paths))