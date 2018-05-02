from flask import *
from http_codes import *

api = Blueprint('api', __name__, template_folder='templates')

@api.route('/api/v1/analyze', methods=['GET'])
def analyze():
    params = request.args

    if 'username' not in params:
        return jsonify({'message': 'Missing the required "username" parameter'})
    elif 'method' not in params:
        return jsonify({'message': 'Missing the requried "method" parameter'})

    return 'username: ' + params['username'] + ', method: ' + params['method']
