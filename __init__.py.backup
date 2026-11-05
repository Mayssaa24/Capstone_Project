import logging

from flask import Flask

from app.config import load_config
from app.errors import register_error_handlers


def create_app(test_config=None):
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    logging.basicConfig(level=logging.INFO)

    app = Flask(__name__)
    config = load_config(test_config)
    app.config.update(config)

    from app.routes import bp
    from app.services import ServiceContainer

    app.extensions["services"] = ServiceContainer(config)
    app.register_blueprint(bp)
    register_error_handlers(app)
    return app
