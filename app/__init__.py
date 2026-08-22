import os
import sys

_MODULOS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modulos")
if _MODULOS_DIR not in sys.path:
    sys.path.insert(0, _MODULOS_DIR)

from flask import Flask


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"),
        static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
    )
    app.config["SECRET_KEY"] = "planificador-dev-key"

    from app.routes import bp
    app.register_blueprint(bp)

    return app
