from flask import Flask
from flask.ext.mail import Mail

app = Flask(__name__,static_folder='static', static_url_path='')
app.config.from_object('config')
mail = Mail(app)

from app import views
