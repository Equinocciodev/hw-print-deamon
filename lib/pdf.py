import os
import uuid
from datetime import datetime
import pdfkit
from sys import platform


def generate(form):
    current_working_directory = os.getcwd()
    pdf_dir = os.path.join(current_working_directory, "pdf")
    # Configuration for wkhtmltopdf
    wkhtmltopdf_dir = os.path.join(current_working_directory, "bin", "wkhtmltopdf.exe")
    if platform == 'darwin':
        wkhtmltopdf_dir = os.path.join("/usr/local/bin/wkhtmltopdf")
        wkhtmltopdf_dir = os.path.join(current_working_directory, "bin", "wkhtmltopdf")
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_dir)
    printer_data=form.get('printer_data')

    os.makedirs(pdf_dir, exist_ok=True)

    filename = datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p") + str(uuid.uuid4()) + '.pdf'
    pdf_file = os.path.join(pdf_dir, filename)

    # default values
    margin_top = '0in',
    margin_right = '0.3in'
    margin_bottom = '0in'
    margin_left = '0.3in'
    font_size = '17px'
    font_family = "'Calibri', sans-serif"
    orientation = 'portrait'
    line_height = 'auto'
    letter_spacing = 'auto'
    header_spacing = '0'
    if str(form.get('orientation')).lower() == 'landscape':
        orientation = 'landscape'
        margin_top = '0in'
        margin_right = '0.78in'
        margin_bottom = '0in'
        margin_left = '0.4in'
        font_size = '13px'
        font_family = "'Courier New', Courier, monospace"
        letter_spacing = 'auto'
        header_spacing = '0'
        line_height = '1.5'

    margin_top = margin_top if not form.get('margin_top') else form.get('margin_top') + 'mm'
    if form.get('margin_top'):
        printer_data=printer_data.replace('<pre class="custom_font_properties">', '').replace('</pre>', '')
    margin_right = margin_right if not form.get('margin_right') else form.get('margin_right') + 'mm'
    margin_left = margin_left if not form.get('margin_left') else form.get('margin_left') + 'mm'
    margin_bottom = margin_bottom if not form.get('margin_bottom') else form.get('margin_bottom') + 'mm'
    font_family = font_family if not form.get('font_family') else form.get('font_family')
    line_height = line_height if not form.get('line_height') else form.get('line_height')
    font_size = font_size if not form.get('font_size') else form.get('font_size') + 'px'
    letter_spacing = letter_spacing if not form.get('letter_spacing') else form.get('letter_spacing') + 'px'
    header_spacing = header_spacing if not form.get('header_spacing') else form.get('header_spacing')

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-size: {font_size}; font-family: {font_family}, sans-serif;letter-spacing: {letter_spacing}; line-height: {line_height};}}
        </style>
    </head>
    <body>
        {printer_data}
    </body>
    </html>
    """
    #print(html_content)
    options = {
        'orientation': f'{orientation}',
        'margin-top': margin_top,
        'margin-right': margin_right,
        'margin-bottom': margin_bottom,
        'margin-left': margin_left,
        'header-spacing': header_spacing,

    }
    paper_format = form.get('format')
    if paper_format:
        if paper_format != "custom":
            options['page-size'] = paper_format
        else:
            if form.get('page_width') and form.get('page_height'):
                options['page-width'] = form.get('page_width') + 'mm'
                options['page-height'] = form.get('page_height') + 'mm'

    print(options)

    # Convert HTML to PDF
    pdfkit.from_string(html_content, pdf_file, configuration=config, options=options)

    return pdf_file
