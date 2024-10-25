from sys import platform
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import dotenv_values
import subprocess

if platform == 'darwin':
    from lib.macos import Printing
else:
    import win32print
    from lib.windows import Printing

app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
@app.route('/dotmatrix/print', methods=['POST'])
def index():
    config = dotenv_values(".env")
    if not request.form.get('printer'):
        request.form['printer'] = config.get('PRINTER')
    Printing().do_print_old(request.form)

    return jsonify({'status': 'OK'})

@app.route('/v2/dotmatrix/print/', methods=['POST'])
def v2_dot_matrix_print():
    config = dotenv_values(".env")
    if not request.form.get('printer'):
        request.form['printer'] = config.get('PRINTER')
    Printing().do_print(request.form)

    return jsonify({'status': 'OK'})

@app.route('/printers', methods=['GET'])
def get_printers():
    if platform == 'darwin':
        result = subprocess.run(['lpstat', '-p'], stdout=subprocess.PIPE)
        printers = [line.split(' ')[1] for line in result.stdout.decode().split('\n') if line]
    else:
        printers = [printer[2] for printer in win32print.EnumPrinters(2)]

    return jsonify({'printers': printers})

if __name__ == '__main__':
    app.run(debug=True, port=8000)