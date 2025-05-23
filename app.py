# app.py

from flask import Flask
from extensions import db, bcrypt, login_manager, migrate, mail, csrf
from routes import main
from models import Usuario
from utils import calcular_precio_total, calcular_tiempo_entrega

def create_app():
    app = Flask(__name__)

    # Configuración de la aplicación

    app.jinja_env.globals.update(calcular_precio_total=calcular_precio_total)
    app.jinja_env.globals.update(calcular_tiempo_entrega=calcular_tiempo_entrega)
    app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Configuración de Flask-Mail
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'matias.redescom@gmail.com'  # Actualiza con tu correo
    app.config['MAIL_PASSWORD'] = 'vnse purs szou cive'  # Usa una contraseña de aplicación si es necesario
    app.config['MAIL_DEFAULT_SENDER'] = ('Tu Nombre', 'tu_correo@gmail.com')  # Actualiza con tu información

    # Inicializar extensiones
    db.init_app(app)
    mail.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)  # Inicializar CSRFProtect
    login_manager.login_view = 'main.login'
    login_manager.login_message_category = 'info'






    # Definir la función user_loader para Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return Usuario.query.get(int(user_id))
        except db.exc.OperationalError:
            # La tabla usuarios no existe aún
            return None
        except Exception as e:
            # Maneja otros posibles errores
            app.logger.error(f"Error al cargar el usuario: {e}")
            return None

    # Registrar blueprints
    app.register_blueprint(main)
    app.jinja_env.globals.update(
    calcular_precio_total=calcular_precio_total,
    calcular_tiempo_entrega=calcular_tiempo_entrega
)
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
