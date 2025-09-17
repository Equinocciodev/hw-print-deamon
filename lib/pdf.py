import os
import uuid
from datetime import datetime
import pdfkit
from .config_store import PDFOrientationConfigStore

def generate(printer_data, orientation):
    current_working_directory = os.getcwd()
    pdf_dir = os.path.join(current_working_directory, "pdf")
    wkhtmltopdf_dir = os.path.join(current_working_directory, "bin", "wkhtmltopdf.exe")
    
    os.makedirs(pdf_dir, exist_ok=True)
    
    filename = datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p") + str(uuid.uuid4()) + '.pdf'
    pdf_file = os.path.join(pdf_dir, filename)
    
    # Configuration for wkhtmltopdf
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_dir)
    print(orientation)
    
    # Load orientation-specific configuration
    pdf_config_store = PDFOrientationConfigStore()
    orientation_config = pdf_config_store.get_orientation_config(str(orientation).lower())
    
    # Extract configuration parameters
    margin_top = orientation_config.get('margin_top', '0in')
    margin_right = orientation_config.get('margin_right', '0.3in')
    margin_bottom = orientation_config.get('margin_bottom', '0in')
    margin_left = orientation_config.get('margin_left', '0.3in')
    font_size = orientation_config.get('font_size', '13px')
    font_family = orientation_config.get('font_family', "'Courier New', Courier, monospace")
    top = orientation_config.get('top', '0px')
    
    # Handle tuple format for margins (backward compatibility)
    if isinstance(margin_top, tuple):
        margin_top = margin_top[0]
    if isinstance(margin_right, tuple):
        margin_right = margin_right[0]
    if isinstance(margin_bottom, tuple):
        margin_bottom = margin_bottom[0]
    if isinstance(margin_left, tuple):
        margin_left = margin_left[0]
       
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                font-size: {font_size}; 
                font-family: {font_family}; 
                position: relative; 
                top: {top};
            }}
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
