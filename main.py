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
elif platform == 'win32' or platform == 'cygwin':
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
    return jsonify({'printers': Printing().get_printers()})


@app.route('/pdf/list', methods=['GET'])
def get_pdf_list():
    pdf_dir = 'pdf'
    pdfs = [f for f in os.listdir(pdf_dir) if os.path.isfile(os.path.join(pdf_dir, f))]

    # Pagination
    page = int(request.args.get('page', 1))
    per_page = 10
    total = len(pdfs)
    start = (page - 1) * per_page
    end = start + per_page
    pdfs_paginated = pdfs[start:end]

    return render_template('pdf_list.html', pdfs=pdfs_paginated, page=page, total=total, per_page=per_page)


@app.route('/pdf/<filename>', methods=['GET'])
def download_pdf(filename):
    pdf_dir = 'pdf'
    return send_from_directory(pdf_dir, filename)


@app.route('/pdf/clear', methods=['POST'])
def pdf_clear():
    return jsonify(clear_pdfs())


if __name__ == '__main__':
    app.run(debug=True, port=8000)
