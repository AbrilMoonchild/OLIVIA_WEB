# /OLIVIA_WEB/olivia_app/__init__.py
from flask import Flask
from flask_cors import CORS
from .config import Config

def create_app():
    app = Flask(__name__, template_folder="../templates")
    app.config.from_object(Config)
    
    CORS(app)
    
    # Registrar Blueprints de Usuarios (sin prefijo)
    from .blueprints.auth import auth_bp
    from .blueprints.user import user_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)

    # Registrar Blueprints de IA (con prefijo /api)
    from .blueprints.predict import predict_bp
    from .blueprints.report import report_bp

    app.register_blueprint(predict_bp, url_prefix='/api')
    app.register_blueprint(report_bp, url_prefix='/api')
    
    print("✅ Aplicación OLIVIA V5.3 creada y Blueprints registrados.")
    return app