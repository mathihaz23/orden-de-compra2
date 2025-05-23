from flask import Flask
from .extensions import db, migrate, login_manager, bcrypt, mail
from .config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)

    # Importar rutas
    with app.app_context():
        from .routes import main
        app.register_blueprint(main)

        db.create_all()

    return app
