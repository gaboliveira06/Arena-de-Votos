from flask import Flask
from config import SECRET_KEY
from database import init_db
from routes.public import public_bp
from routes.admin import admin_bp


def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    init_db()
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    return app


app = create_app()

if __name__ == "__main__":
    print("\nArena de Votos — versão full stack final")
    print("Público: http://localhost:5000")
    print("Admin:   http://localhost:5000/admin")
    app.run(debug=True, host="0.0.0.0", port=5000)
