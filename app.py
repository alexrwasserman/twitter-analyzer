from flask import Flask, render_template

# Initialize Flask app with the template folder address
app = Flask(__name__, template_folder='templates')
