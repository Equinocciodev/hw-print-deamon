from sys import platform

from dotenv import dotenv_values
from flask import Flask
from flask import jsonify
from flask import request
from flask_cors import CORS, cross_origin

if platform == 'darwin':
    from lib.macos import Printing
else:
    from lib.windows import Printing
app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
@app.route('/dotmatrix/print', methods=['POST'])
def index():
    
    config = dotenv_values(".env")
    if request.form['orientation'] in ['landscape']:
        printer = config['PRINTER_NAME_LANDSCAPE']
    elif request.form['orientation'] in ['portrait']:
        printer = config['PRINTER_NAME_PORTRAIT']
    
    PrintingQueu = Printing()
    PrintingQueu.print(request.form['printer_data'], request.form['orientation'], printer)
    out = {'status': 'OK'}
    return jsonify(out)

@app.route('/', methods=['GET'])
def home():
    config = dotenv_values(".env")
    out = {'status': 'OK',
           'printer': config['PRINTER_NAME'],
           'os': platform,}
    return jsonify(out)

if __name__ == '__main__':
    app.run(port=8000)