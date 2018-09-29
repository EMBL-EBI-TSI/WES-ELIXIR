from inspect import stack
import logging

from celery import Celery

from wes_elixir.config.config_parser import (get_conf, get_conf_type)


# Get logger instance
logger = logging.getLogger(__name__)


def create_celery_app(app):

    # Re-assign config values
    broker=get_conf(app.app.config, 'celery', 'broker_url')
    backend=get_conf(app.app.config, 'celery', 'result_backend')
    include=get_conf_type(app.app.config, 'celery', 'include', types=(list))
    maxsize=get_conf(app.app.config, 'celery', 'message_maxsize')

    # Instantiate Celery app
    celery = Celery(
        app=__name__,
        broker=broker,
        backend=backend,
        include=include,
    )
    logger.info("Celery app created from '{calling_module}'.".format(
        calling_module=':'.join([stack()[1].filename, stack()[1].function])
    ))

    # Set Celery options
    # TODO: Fix to get around message truncation problem
    # TODO: Possibly try to solve this differently (via result backend?) as this may not very robust
    celery.Task.resultrepr_maxsize = maxsize
    celery.amqp.argsrepr_maxsize = maxsize
    celery.amqp.kwargsrepr_maxsize = maxsize

    # Update Celery app configuration with Flask app configuration
    celery.conf.update(app.app.config)
    logger.info("Celery app configured.")

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    logger.debug("App context added to celery.Task class.")

    return celery