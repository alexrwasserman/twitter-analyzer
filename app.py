import os
from flask import Flask, render_template
import controllers

# Initialize Flask app with the template folder address
app = Flask(__name__, template_folder='templates')

app.register_blueprint(controllers.main)
app.register_blueprint(controllers.api)

if __name__ == '__main__':
    if not os.path.exists('tweets'):
        os.makedirs('tweets')

    app.run(host='0.0.0.0', port=8080, debug=True)
