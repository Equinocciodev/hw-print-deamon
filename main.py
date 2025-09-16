from sys import platform
import logging
import threading

from dotenv import dotenv_values
from flask import Flask, jsonify, request
from flask_cors import CORS, cross_origin
import win32print
import subprocess

if platform == 'darwin':
    from lib.macos import Printing
else:
    from lib.windows import Printing

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

# Global printing instance
printing_service = Printing()

@app.route('/dotmatrix/print', methods=['POST'])
@cross_origin()
def index():
    """
    Print endpoint - maintains exact compatibility with call_to_api.js
    Accepts: printer_data, orientation, printer
    Returns: {'status': 'OK'} on success
    """
    try:
        # Extract form data (same as original)
        printer_data = request.form.get('printer_data')
        orientation = request.form.get('orientation')
        printer = request.form.get('printer')
        
        # Validate required parameters
        if not printer_data:
            logger.error("Missing printer_data in request")
            return jsonify({'status': 'ERROR', 'message': 'Missing printer_data'}), 400
        
        if not orientation:
            logger.error("Missing orientation in request")
            return jsonify({'status': 'ERROR', 'message': 'Missing orientation'}), 400
        
        if not printer:
            logger.error("Missing printer in request")
            return jsonify({'status': 'ERROR', 'message': 'Missing printer'}), 400
        
        logger.info(f"Print request received: printer={printer}, orientation={orientation}")
        
        # Check if printer is configured for this orientation
        if not printing_service.is_printer_configured(printer, orientation.lower()):
            error_msg = f"Printer '{printer}' is not configured for {orientation} orientation. Please configure it in the Print Queue Manager."
            logger.error(error_msg)
            return jsonify({'status': 'ERROR', 'message': error_msg}), 400
        
        # Submit print job using the enhanced printing service
        success = printing_service.print(printer_data, orientation, printer)
        
        if success:
            logger.info(f"Print job submitted successfully to {printer}")
            # Return exact same response format as original
            return jsonify({'status': 'OK'})
        else:
            logger.error(f"Failed to submit print job to {printer}")
            return jsonify({'status': 'ERROR', 'message': 'Print job submission failed'}), 500
            
    except Exception as e:
        logger.error(f"Error in print endpoint: {e}")
        return jsonify({'status': 'ERROR', 'message': str(e)}), 500

@app.route('/printers', methods=['GET'])
@cross_origin()
def get_printers():
    """
    Printers endpoint - maintains exact compatibility with call_to_api.js
    Returns: {'printers': [list_of_printer_names]}
    """
    try:
        printers = []
        if platform == 'Darwin':
            result = subprocess.run(['lpstat', '-p'], stdout=subprocess.PIPE)
            printers = [line.split(' ')[1] for line in result.stdout.decode().split('\n') if line] 
        else:
            # Use enhanced printer service
            printers = printing_service.get_printers()
            logger.info(f"Found {len(printers)} printers")

        # Return exact same response format as original
        return jsonify({'printers': printers})
        
    except Exception as e:
        logger.error(f"Error in printers endpoint: {e}")
        return jsonify({'printers': []}), 500

# Additional endpoint for printer status (optional, not used by Odoo)
@app.route('/printer-status', methods=['GET'])
@cross_origin()
def get_printer_status():
    """
    Optional endpoint to get printer configuration status.
    Not used by call_to_api.js, but useful for debugging.
    """
    try:
        printer_name = request.args.get('printer')
        
        if printer_name:
            status = printing_service.get_printer_status(printer_name)
            configs = printing_service.get_printer_configurations(printer_name)
        else:
            status = printing_service.get_printer_status()
            configs = printing_service.get_printer_configurations()
        
        return jsonify({
            'status': status,
            'configurations': configs
        })
        
    except Exception as e:
        logger.error(f"Error in printer-status endpoint: {e}")
        return jsonify({'error': str(e)}), 500

# Additional endpoint for queue status (optional, not used by Odoo)
@app.route('/queue-status', methods=['GET'])
@cross_origin()
def get_queue_status():
    """
    Optional endpoint to get print queue status.
    Not used by call_to_api.js, but useful for monitoring.
    """
    try:
        status = printing_service.get_printer_status()
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error in queue-status endpoint: {e}")
        return jsonify({'error': str(e)}), 500

def shutdown_handler():
    """Graceful shutdown handler"""
    logger.info("Shutting down print service...")
    try:
        printing_service.shutdown()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Register shutdown handler
import atexit
atexit.register(shutdown_handler)

if __name__ == '__main__':
    logger.info("Starting Print Daemon API Server")
    logger.info("Endpoints:")
    logger.info("  POST /dotmatrix/print - Submit print job (compatible with call_to_api.js)")
    logger.info("  GET /printers - List available printers (compatible with call_to_api.js)")
    logger.info("  GET /printer-status - Get printer configuration status (optional)")
    logger.info("  GET /queue-status - Get print queue status (optional)")
    
    try:
        app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Error running Flask app: {e}")
    finally:
        shutdown_handler()