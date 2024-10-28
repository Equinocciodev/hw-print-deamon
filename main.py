import subprocess
from sys import platform

from dotenv import dotenv_values
from flask import Flask, jsonify, request
from flask_cors import CORS

if platform == 'darwin':
    from lib.macos import Printing
else:
    import win32print
    from lib.windows import Printing

app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'


@app.route('/')
def index():
    return jsonify({'status': 'OK'})

@app.route('/dotmatrix/print', methods=['POST'])
def dotmatrix_print():
    config = dotenv_values(".env")
    form =request.form.copy()
    if not request.form.get('printer'):
        form['printer'] = config.get('PRINTER_NAME')

    Printing().do_print(form)

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