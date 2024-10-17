from sys import platform

from dotenv import dotenv_values
from flask import Flask
from flask import jsonify
from flask import request
from flask_cors import CORS, cross_origin
import win32print
import subprocess

if platform == 'darwin':
    from lib.macos import Printing
else:
    from lib.windows import Printing
app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
@app.route('/dotmatrix/print', methods=['POST'])
def index():
    
    PrintingQueu = Printing()
    PrintingQueu.print(request.form['printer_data'], request.form['orientation'], request.form['printer'])
    out = {'status': 'OK'}
    return jsonify(out)

@app.route('/printers', methods=['GET'])
def get_printers():
    printers = []
    if platform == 'Darwin':
        result = subprocess.run(['lpstat', '-p'], stdout=subprocess.PIPE)
        printers = [line.split(' ')[1] for line in result.stdout.decode().split('\n') if line] 
    else:
        printers = [printer[2] for printer in win32print.EnumPrinters(2)]
        print(printers)

    return jsonify({'printers': printers})

if __name__ == '__main__':
    app.run(port=8000)