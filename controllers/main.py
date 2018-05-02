from flask import *
from http_codes import *

main = Blueprint('main', __name__, template_folder='templates')

@main.route('/', methods=['GET'])
def main_route():
    return render_template('index.html')
