import os
import uuid
from datetime import datetime
from sys import platform

import pdfkit

CWD = os.getcwd()
PDF_DIR = os.path.join(CWD, "pdf")

def generate(form):
    os.makedirs(PDF_DIR, exist_ok=True)
    wkhtmltoPDF_DIR = os.path.join(CWD, "bin", "wkhtmltopdf.exe") if platform in ['win32', 'cygwin'] else \
        os.path.join("/usr/local/bin/wkhtmltopdf") if platform == 'darwin' else \
            os.path.join(CWD, "bin", "wkhtmltopdf")
    if not os.path.exists(wkhtmltoPDF_DIR):
        raise FileNotFoundError(f"wkhtmltopdf not found in {wkhtmltoPDF_DIR}")

    config = pdfkit.configuration(wkhtmltopdf=wkhtmltoPDF_DIR)
    printer_data = form.get('printer_data')
    filename = f"{datetime.now().strftime('%Y_%m_%d-%I_%M_%S_%p')}{uuid.uuid4()}.pdf"
    pdf_file = os.path.join(PDF_DIR, filename)

    orientation = 'landscape' if form.get('orientation', '').lower() == 'landscape' else 'portrait'
    margins = {
        'portrait': {'top': '0in', 'right': '0.3in', 'bottom': '0in', 'left': '0.3in', 'font_size': '17px',
                     'font_family': "'Calibri', sans-serif"},
        'landscape': {'top': '0in', 'right': '0.78in', 'bottom': '0in', 'left': '0.4in', 'font_size': '13px',
                      'font_family': "'Courier New', Courier, monospace"}
    }
    margin = margins[orientation]
    margin.update(
        {k: f"{form.get(k)}mm" for k in ['margin_top', 'margin_right', 'margin_bottom', 'margin_left'] if form.get(k)})
    margin.update(
        {k: form.get(k) for k in ['font_family', 'line_height', 'font_size', 'letter_spacing', 'header_spacing'] if
         form.get(k)})

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-size: {margin['font_size']}; font-family: {margin['font_family']}; letter-spacing: {margin.get('letter_spacing', 'initial')}; line-height: {margin.get('line_height', 'initial')}; }}
        </style>
    </head>
    <body>
        {printer_data}
    </body>
    </html>
    """

    options = {
        'orientation': orientation,
        'margin-top': margin['top'],
        'margin-right': margin['right'],
        'margin-bottom': margin['bottom'],
        'margin-left': margin['left'],
        'header-spacing': margin.get('header_spacing', '0')
    }
    if form.get('format') and form.get('format') != '0':
        if form.get('format') != "custom":
            options['page-size'] = form.get('format')
        else:
            options.update({'page-width': f"{form.get('page_width')}mm", 'page-height': f"{form.get('page_height')}mm"})

    pdfkit.from_string(html_content, pdf_file, configuration=config, options=options)
    return pdf_file

def clear_pdfs():
    for filename in os.listdir(PDF_DIR):
        file_path = os.path.join(PDF_DIR, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    return {'status': 'OK', 'message': 'All PDFs cleared'}