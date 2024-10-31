import os
import uuid
from datetime import datetime
from sys import platform

import pdfkit

CWD = os.getcwd()
PDF_DIR = os.path.join(CWD, "pdf")


def generate(form):
    os.makedirs(PDF_DIR, exist_ok=True)
    wkhtmltopdf_dir = os.path.join(CWD, "bin", "wkhtmltopdf.exe") if platform in ['win32', 'cygwin'] else \
        os.path.join("/usr/local/bin/wkhtmltopdf") if platform == 'darwin' else \
            os.path.join(CWD, "bin", "wkhtmltopdf")
    if not os.path.exists(wkhtmltopdf_dir):
        raise FileNotFoundError(f"wkhtmltopdf not found in {wkhtmltopdf_dir}")

    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_dir)
    printer_data = form.get('printer_data')
    filename = f"{datetime.now().strftime('%Y_%m_%d-%I_%M_%S_%p')}{uuid.uuid4()}.pdf"
    pdf_file = os.path.join(PDF_DIR, filename)

    orientation = 'landscape' if form.get('orientation', '').lower() == 'landscape' else 'portrait'
    margins = {
        'portrait': {'margin_top': '0in', 'margin_right': '0.3in', 'margin_bottom': '0in', 'margin_left': '0.3in',
                     'font_size': '9',
                     'font_family': "'Arial', sans-serif"},
        'landscape': {'margin_top': '0in', 'margin_right': '0.78in', 'margin_bottom': '0in', 'margin_left': '0.4in',
                      'font_size': '13',
                      'font_family': "'Courier New', Courier, monospace"}
    }
    margin = margins[orientation]
    margin.update(
        {k: f"{form.get(k)}mm" for k in ['margin_top', 'margin_right', 'margin_bottom', 'margin_left'] if form.get(k)})
    margin.update(
        {k: form.get(k) for k in ['font_family', 'line_height', 'font_size', 'letter_spacing', 'header_spacing'] if
         form.get(k)})

    if form.get('margin_top'):
        printer_data = printer_data.replace('<pre class="custom_font_properties">', '').replace('</pre>', '')

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-size: {margin['font_size']}px; font-family: {margin['font_family']}; letter-spacing: {margin.get('letter_spacing', 'initial')}px; line-height: {margin.get('line_height', 'initial')}; }}
        </style>
    </head>
    <body>
        {printer_data}
    </body>
    </html>
    """


    options = {
        'orientation': orientation,
        'margin-top': margin['margin_top'],
        'margin-right': margin['margin_right'],
        'margin-bottom': margin['margin_bottom'],
        'margin-left': margin['margin_left'],
        'header-spacing': margin.get('header_spacing', '0')
    }
    print(margin)
    print(options)
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
