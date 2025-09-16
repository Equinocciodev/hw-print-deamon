import win32print
import logging
from lib.print_manager import print_queue_manager
from lib.config_store import printer_config_store

logger = logging.getLogger(__name__)

class Printing(object):
    """
    Enhanced Printing class that uses the new print queue manager
    and stored printer configurations.
    """
    
    def print(self, printer_data, orientation, printer):
        """
        Submit a print job to the queue manager.
        
        Args:
            printer_data: HTML/data to print
            orientation: "portrait" or "landscape"
            printer: Name of the target printer
        """
        try:
            # Submit job to print queue manager
            job_id = print_queue_manager.submit_print_job(
                printer_name=printer,
                printer_data=printer_data,
                orientation=orientation
            )
            
            if job_id:
                logger.info(f"Print job {job_id} submitted successfully to {printer}")
                return True
            else:
                logger.error(f"Failed to submit print job to {printer}")
                return False
                
        except Exception as e:
            logger.error(f"Error submitting print job: {e}")
            return False
    
    def get_printers(self):
        """Get list of available printers"""
        try:
            # Use the queue manager's method which includes queue management
            return print_queue_manager.get_available_printers()
        except Exception as e:
            logger.error(f"Error getting printers from queue manager: {e}")
            # Fall back to direct Win32 call
            return [printer[2] for printer in win32print.EnumPrinters(2)]
    
    def get_printer_status(self, printer_name=None):
        """
        Get printer status and queue information.
        
        Args:
            printer_name: Specific printer name, or None for all printers
            
        Returns:
            Dictionary with printer status information
        """
        try:
            if printer_name:
                return print_queue_manager.get_printer_queue_status(printer_name)
            else:
                return print_queue_manager.get_all_queue_status()
        except Exception as e:
            logger.error(f"Error getting printer status: {e}")
            return {}
    
    def is_printer_configured(self, printer_name, orientation):
        """
        Check if a printer is configured for a specific orientation.
        
        Args:
            printer_name: Name of the printer
            orientation: "portrait" or "landscape"
            
        Returns:
            True if configured, False otherwise
        """
        try:
            return printer_config_store.is_configured(printer_name, orientation)
        except Exception as e:
            logger.error(f"Error checking printer configuration: {e}")
            return False
    
    def get_printer_configurations(self, printer_name=None):
        """
        Get printer configuration information.
        
        Args:
            printer_name: Specific printer name, or None for all printers
            
        Returns:
            Dictionary with configuration information
        """
        try:
            if printer_name:
                return printer_config_store.get_printer_configurations(printer_name)
            else:
                return printer_config_store.get_all_configurations()
        except Exception as e:
            logger.error(f"Error getting printer configurations: {e}")
            return {}
    
    def refresh_printers(self):
        """Refresh the printer list and queues"""
        try:
            print_queue_manager.refresh_printer_queues()
            logger.info("Printer list refreshed")
        except Exception as e:
            logger.error(f"Error refreshing printers: {e}")
    
    def shutdown(self):
        """Shutdown the printing system"""
        try:
            print_queue_manager.shutdown()
            logger.info("Printing system shutdown complete")
        except Exception as e:
            logger.error(f"Error during printing system shutdown: {e}") 