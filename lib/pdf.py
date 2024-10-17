import os
import uuid
from datetime import datetime
import pdfkit

def generate(printer_data, orientation):
    current_working_directory = os.getcwd()
    pdf_dir = os.path.join(current_working_directory, "pdf")
    
    os.makedirs(pdf_dir, exist_ok=True)
    
    filename = datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p") + str(uuid.uuid4()) + '.pdf'
    pdf_file = os.path.join(pdf_dir, filename)
    
    
    # Configuration for wkhtmltopdf
    path_wkhtmltopdf = r'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe'  # Update this path as needed
    config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
    
    if orientation == 'landscape':
        html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-size: 13px; font-family: 'Courier New', Courier, monospace;}}
        </style>
    </head>
    <body>
        {printer_data}
    </body>
    </html>
    """
    
        options = {
            'orientation': f'{orientation}',
            'margin-top': '0in',
            'margin-right': '0.78in',
            'margin-bottom': '0in',
            'margin-left': '0.4in',
        }
    elif orientation == 'portrait':
        html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-size: 17px; font-family: 'Calibri', sans-serif;}}
        </style>
    </head>
    <body>
        {printer_data}
    </body>
    </html>
    """
    
        options = {
            'orientation': f'{orientation}',
            'margin-top': '0in',
            'margin-right': '0.3in',
            'margin-bottom': '0in',
            'margin-left': '0.3in',
        }
        
    print(printer_data)
    
    # Convert HTML to PDF
    pdfkit.from_string(html_content, pdf_file, configuration=config, options=options)
    
    return pdf_file
