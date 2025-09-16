"""
Print Daemon Main Launcher
Launches both Flask API server and PyQt GUI interface in separate threads
"""
import sys
import threading
import logging
import signal
import time
from typing import Optional

# Setup logging before importing other modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('print_daemon.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Import after logging setup
from main import app, printing_service
from lib.qt_ui import run_gui
from PyQt6.QtWidgets import QApplication


class PrintDaemon:
    """Main daemon class that manages both API server and GUI"""
    
    def __init__(self):
        self.flask_thread: Optional[threading.Thread] = None
        self.gui_app: Optional[QApplication] = None
        self.running = False
        self.shutdown_event = threading.Event()
    
    def start_flask_server(self):
        """Start Flask API server in a separate thread"""
        try:
            logger.info("Starting Flask API server thread...")
            
            def run_flask():
                try:
                    logger.info("Flask API server starting on http://0.0.0.0:8000")
                    logger.info("API Endpoints:")
                    logger.info("  POST /dotmatrix/print - Submit print job")
                    logger.info("  GET /printers - List available printers")
                    logger.info("  GET /printer-status - Get printer status (optional)")
                    logger.info("  GET /queue-status - Get queue status (optional)")
                    
                    # Run Flask with threading enabled for concurrent requests
                    app.run(
                        host='0.0.0.0', 
                        port=8000, 
                        debug=False, 
                        threaded=True,
                        use_reloader=False  # Important: disable reloader in thread
                    )
                except Exception as e:
                    logger.error(f"Error in Flask server thread: {e}")
            
            self.flask_thread = threading.Thread(target=run_flask, daemon=True)
            self.flask_thread.start()
            
            # Give Flask a moment to start
            time.sleep(2)
            logger.info("Flask API server thread started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Flask server: {e}")
            raise
    
    def start_gui(self):
        """Start PyQt GUI interface"""
        try:
            logger.info("Starting PyQt GUI interface...")
            
            # Create QApplication if it doesn't exist
            if QApplication.instance() is None:
                self.gui_app = QApplication(sys.argv)
                self.gui_app.setApplicationName("Print Queue Manager")
                self.gui_app.setApplicationVersion("1.0")
            else:
                self.gui_app = QApplication.instance()
            
            # Run the GUI - this will block until GUI is closed
            exit_code = run_gui()
            logger.info(f"GUI closed with exit code: {exit_code}")
            
            return exit_code
            
        except Exception as e:
            logger.error(f"Error starting GUI: {e}")
            raise
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown()
        
        # Handle common shutdown signals
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Windows specific
        if sys.platform == "win32":
            try:
                signal.signal(signal.SIGBREAK, signal_handler)
            except AttributeError:
                pass  # SIGBREAK not available on all Windows versions
    
    def start(self):
        """Start the complete daemon (API server + GUI)"""
        try:
            logger.info("=" * 60)
            logger.info("Print Queue Manager Daemon Starting")
            logger.info("=" * 60)
            
            self.running = True
            
            # Setup signal handlers for graceful shutdown
            self.setup_signal_handlers()
            
            # Start Flask API server in background thread
            self.start_flask_server()
            
            # Verify Flask server is running
            if not self.flask_thread or not self.flask_thread.is_alive():
                raise Exception("Failed to start Flask API server")
            
            logger.info("Print daemon API server is ready")
            logger.info("Starting GUI interface...")
            
            # Start GUI (this will block until GUI is closed)
            exit_code = self.start_gui()
            
            logger.info("GUI interface closed, shutting down daemon...")
            self.shutdown()
            
            return exit_code
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
            self.shutdown()
            return 0
            
        except Exception as e:
            logger.error(f"Error starting daemon: {e}")
            self.shutdown()
            return 1
    
    def shutdown(self):
        """Graceful shutdown of all components"""
        if not self.running:
            return
        
        logger.info("Initiating daemon shutdown...")
        self.running = False
        self.shutdown_event.set()
        
        try:
            # Shutdown printing service
            logger.info("Shutting down printing service...")
            printing_service.shutdown()
            
            # Close GUI if running
            if self.gui_app:
                try:
                    logger.info("Closing GUI application...")
                    self.gui_app.quit()
                except Exception as e:
                    logger.error(f"Error closing GUI: {e}")
            
            # Flask server will shutdown when main thread ends (daemon thread)
            logger.info("Flask API server will shutdown automatically")
            
            logger.info("Print daemon shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


def run_api_only():
    """Run only the API server without GUI (for headless operation)"""
    try:
        logger.info("=" * 60)
        logger.info("Print Queue Manager API Server (Headless Mode)")
        logger.info("=" * 60)
        
        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            printing_service.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Starting Flask API server...")
        logger.info("API Endpoints:")
        logger.info("  POST /dotmatrix/print - Submit print job")
        logger.info("  GET /printers - List available printers")
        logger.info("  GET /printer-status - Get printer status")
        logger.info("  GET /queue-status - Get queue status")
        logger.info("")
        logger.info("Note: GUI is not available in headless mode.")
        logger.info("Use the GUI mode to configure printers.")
        
        # Run Flask directly
        app.run(
            host='0.0.0.0',
            port=8000,
            debug=False,
            threaded=True
        )
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in API-only mode: {e}")
    finally:
        printing_service.shutdown()


def main():
    """Main entry point"""
    try:
        # Check command line arguments
        if len(sys.argv) > 1:
            if sys.argv[1] == "--api-only" or sys.argv[1] == "--headless":
                run_api_only()
                return 0
            elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
                print("Print Queue Manager Daemon")
                print("")
                print("Usage:")
                print("  python daemon_main.py           # Run with GUI interface")
                print("  python daemon_main.py --api-only   # Run API server only (headless)")
                print("  python daemon_main.py --headless   # Same as --api-only")
                print("  python daemon_main.py --help       # Show this help")
                print("")
                print("The daemon provides:")
                print("  - REST API compatible with Odoo (call_to_api.js)")
                print("  - GUI interface for printer configuration")
                print("  - Print queue management with logical queues")
                print("  - Native Windows PrintDlgEx integration")
                return 0
        
        # Default: run with GUI
        daemon = PrintDaemon()
        return daemon.start()
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)