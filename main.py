import os
from sys import platform

from dotenv import dotenv_values
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS

from lib.pdf import clear_pdfs

if platform == 'darwin':
    from lib.macos import Printing
elif platform == 'linux':
    from lib.linux import Printing
else:
    from lib.windows import Printing

app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify({'status': 'OK'})

@app.route('/api/print', methods=['POST'])
@app.route('/dotmatrix/print', methods=['POST'])
def api_print():
    config = dotenv_values(".env")
    form = request.form.copy()
    form.setdefault('printer', config.get('PRINTER_NAME'))
    Printing().do_print(form)
    return jsonify({'status': 'OK', 'message': 'Print job added to queue'})

@app.route('/api/printers', methods=['GET'])
@app.route('/printers', methods=['GET'])
def get_printers():
    printers = Printing().get_printers()
    config = dotenv_values(".env")
    default_printer = config.get('PRINTER_NAME')

    if default_printer in printers:
        printers.remove(default_printer)
        printers.insert(0, default_printer)

    return jsonify({'printers': printers})

@app.route('/pdf/list', methods=['GET'])
def get_pdf_list():
    pdf_dir = 'pdf'
    pdfs = [f for f in os.listdir(pdf_dir) if os.path.isfile(os.path.join(pdf_dir, f))]
    page = int(request.args.get('page', 1))
    per_page = 10
    start = (page - 1) * per_page
    pdfs_paginated = pdfs[start:start + per_page]
    return render_template('pdf_list.html', pdfs=pdfs_paginated, page=page, total=len(pdfs), per_page=per_page)

@app.route('/pdf/<filename>', methods=['GET'])
def download_pdf(filename):
    return send_from_directory('pdf', filename)

@app.route('/pdf/clear', methods=['POST'])
def pdf_clear():
    return jsonify(clear_pdfs())


def save_default_printer(printer_name):
    lines = []
    if os.path.exists('.env'):
        with open('.env', 'r') as file:
            lines = file.readlines()

    with open('.env', 'w') as file:
        found = False
        for line in lines:
            if line.startswith('PRINTER_NAME='):
                file.write(f'PRINTER_NAME={printer_name}\n')
                found = True
            else:
                file.write(line)
        if not found:
            file.write(f'PRINTER_NAME={printer_name}\n')


@app.route('/printers/select', methods=['GET', 'POST'])
def select_printer():
    message = None
    if request.method == 'POST':
        selected_printer = request.form.get('printer')
        save_default_printer(selected_printer)
        message = f'{selected_printer} has been set as the default printer.'

    printers = Printing().get_printers()
    config = dotenv_values(".env")
    default_printer = config.get('PRINTER_NAME')
    return render_template('select_printer.html', printers=printers, default_printer=default_printer, message=message)
if __name__ == '__main__':
    app.run(debug=True, port=8000)