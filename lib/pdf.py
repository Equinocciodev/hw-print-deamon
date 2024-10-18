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
        margin_top = '0in',
        margin_right = '0.78in',
        margin_bottom = '0in',
        margin_left = '0.4in',
        font_size = '13px'
        font_family = "'Courier New', Courier, monospace"
        
    elif orientation == 'portrait':
        margin_top = '0in',
        margin_right = '0.3in',
        margin_bottom = '0in',
        margin_left = '0.3in',
        font_size = '17px'
        font_family = "'Calibri', sans-serif"
       
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-size: {font_size}; font-family: {font_family};}}
        </style>
    </head>
    <body>
        {printer_data}
    </body>
    </html>
    """
    
    options = {
        'orientation': f'{orientation}',
        'margin-top': margin_top,
        'margin-right': margin_right,
        'margin-bottom': margin_bottom,
        'margin-left': margin_left,
    }   
        
        
    print(printer_data)
    
    # Convert HTML to PDF
    pdfkit.from_string(html_content, pdf_file, configuration=config, options=options)
    
    return pdf_file
