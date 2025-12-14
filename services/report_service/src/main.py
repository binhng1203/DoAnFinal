from flask import Flask
from src.config import Config
from src.extensions import db, ma, jwt
from src.api.v1.reports import reports_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Init extensions
    db.init_app(app)
    ma.init_app(app)
    jwt.init_app(app)

    # Register Blueprints
    app.register_blueprint(reports_bp)

    @app.route('/health')
    def health():
        return {"status": "ok"}, 200

    return app

if __name__ == '__main__':
    app = create_app()
    # Chạy host 0.0.0.0 để Docker access được
    app.run(host='0.0.0.0', port=8000, debug=True)