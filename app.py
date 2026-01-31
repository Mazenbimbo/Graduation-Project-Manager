from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.secret_key = 'SOME KEY'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///./data.db'
    app.config['UPLOAD_FOLDER'] = '/home/mazen/gpm/static/uploads/'
    db.init_app(app)
    from routes import register_routes
    register_routes(app,db)

    migrate = Migrate(app,db)

    return app
