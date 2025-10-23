"""
Print Manager with Logical Queues
Manages logical print queues per printer and processes jobs using stored configurations
"""
import threading
import queue
import time
import uuid
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from lib.config_store import printer_config_store
from lib import pdf
import win32print
import win32api

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Print job status enumeration"""
    QUEUED = "queued"
    PROCESSING = "processing"
    PRINTING = "printing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PrintJob:
    """Represents a print job with all necessary information"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    printer_name: str = ""
    printer_data: str = ""
    orientation: str = "portrait"
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    pdf_file: str = ""
    pages: int = 1
    sequence_number: Optional[int] = None  # For tracking order within printer queue
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        return {
            'id': self.id,
            'printer_name': self.printer_name,
            'orientation': self.orientation,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'pdf_file': self.pdf_file,
            'pages': self.pages,
            'sequence_number': self.sequence_number
        }


class PrinterQueue:
    """Logical queue for a specific printer"""
    
    def __init__(self, printer_name: str):
        self.printer_name = printer_name
        self.printer_type = "local"  # Default type, will be updated when detected
        self.queue = queue.Queue()
        self.current_job: Optional[PrintJob] = None
        self.job_history: List[PrintJob] = []
        self.is_processing = False
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.sequence_counter = 0  # For tracking job order
        self.sequence_lock = threading.Lock()  # Thread-safe sequence numbering
        
        # Start worker thread
        self.start_worker()
    
    def start_worker(self):
        """Start the worker thread for this queue"""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.stop_event.clear()
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            logger.info(f"Started worker thread for printer: {self.printer_name}")
    
    def stop_worker(self):
        """Stop the worker thread"""
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_event.set()
            self.worker_thread.join(timeout=5)
            logger.info(f"Stopped worker thread for printer: {self.printer_name}")
    
    def add_job(self, job: PrintJob) -> bool:
        """Add a job to the queue with sequential numbering"""
        try:
            # Assign sequence number for order tracking
            with self.sequence_lock:
                self.sequence_counter += 1
                job.sequence_number = self.sequence_counter
            
            job.status = JobStatus.QUEUED
            self.queue.put(job)
            logger.info(f"Added job {job.id} (seq #{job.sequence_number}) to queue for printer {self.printer_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add job to queue: {e}")
            return False
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            'printer_name': self.printer_name,
            'printer_type': self.printer_type,
            'queue_size': self.queue.qsize(),
            'is_processing': self.is_processing,
            'current_job': self.current_job.to_dict() if self.current_job else None,
            'recent_jobs': [job.to_dict() for job in self.job_history[-10:]]  # Last 10 jobs
        }
    
    def _is_windows_printer_queue_empty(self) -> bool:
        """Check if Windows printer queue is empty (no pending jobs)"""
        try:
            # Get printer handle
            printer_handle = win32print.OpenPrinter(self.printer_name)
            
            try:
                # Get printer info including job count
                printer_info = win32print.GetPrinter(printer_handle, 2)
                job_count = printer_info.get('cJobs', 0)
                
                logger.debug(f"Windows queue for {self.printer_name} has {job_count} jobs")
                return job_count == 0
                
            finally:
                win32print.ClosePrinter(printer_handle)
                
        except Exception as e:
            logger.warning(f"Could not check Windows queue status for {self.printer_name}: {e}")
            # If we can't check, assume it's safe to proceed
            return True
    
    def _worker_loop(self):
        """Main worker loop for processing jobs"""
        logger.info(f"Worker loop started for printer: {self.printer_name}")
        
        while not self.stop_event.is_set():
            try:
                # Get next job with timeout
                try:
                    job = self.queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                self.current_job = job
                self.is_processing = True
                
                seq_info = f" (seq #{job.sequence_number})" if job.sequence_number else ""
                logger.info(f"Worker for {self.printer_name} picked up job {job.id}{seq_info} from queue")
                
                # Process the job
                self._process_job(job)
                
                # Mark queue task as done
                self.queue.task_done()
                logger.info(f"Worker for {self.printer_name} completed job {job.id}{seq_info}")
                
            except Exception as e:
                seq_info = f" (seq #{self.current_job.sequence_number})" if hasattr(self, 'current_job') and self.current_job and self.current_job.sequence_number else ""
                logger.error(f"Error in worker loop for {self.printer_name} processing job {self.current_job.id if hasattr(self, 'current_job') and self.current_job else 'unknown'}{seq_info}: {e}")
                if hasattr(self, 'current_job') and self.current_job:
                    self.current_job.status = JobStatus.FAILED
                    self.current_job.error_message = str(e)
                    self.job_history.append(self.current_job)
                    self.queue.task_done()
                time.sleep(1)
            finally:
                self.current_job = None
                self.is_processing = False
        
        logger.info(f"Worker loop stopped for printer: {self.printer_name}")
    
    def _process_job(self, job: PrintJob):
        """Process a single print job using native Windows printing"""
        try:
            self.current_job = job
            self.is_processing = True
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now()
            
            seq_info = f" (seq #{job.sequence_number})" if job.sequence_number else ""
            logger.info(f"Processing job {job.id}{seq_info} for printer {job.printer_name}")
            
            # CRITICAL: Wait for Windows printer queue to be empty before proceeding
            # This ensures sequential processing and prevents correlative jumps
            logger.info(f"Waiting for Windows queue to be empty for {job.printer_name}{seq_info}...")
            max_wait_time = 300  # 5 minutes maximum wait
            wait_start = time.time()
            
            while not self._is_windows_printer_queue_empty():
                if time.time() - wait_start > max_wait_time:
                    logger.warning(f"Timeout waiting for Windows queue to clear for {job.printer_name}{seq_info}")
                    break
                    
                logger.debug(f"Windows queue not empty for {job.printer_name}{seq_info}, waiting 2 seconds...")
                time.sleep(2)
                
                # Check if we should stop
                if self.stop_event.is_set():
                    raise Exception("Worker stopped while waiting for queue")
            
            logger.info(f"Windows queue is ready for {job.printer_name}, proceeding with job {job.id}{seq_info}")
            
            # Check if printer configuration exists
            config_data = printer_config_store.load_printer_config(
                job.printer_name, job.orientation.lower())
            
            if not config_data:
                raise Exception(f"No configuration found for {job.printer_name}:{job.orientation}")
            
            devmode_data, devnames_data, metadata = config_data
            
            # Generate PDF
            job.status = JobStatus.PROCESSING
            job.pdf_file = pdf.generate(job.printer_data, job.orientation)
            
            if not job.pdf_file:
                raise Exception("Failed to generate PDF")
            
            # Apply printer configuration and print using native Windows API
            job.status = JobStatus.PRINTING
            
            # For dot-matrix printers, try Ghostscript method first
            if any(model in job.printer_name.upper() for model in ['FX-2190', 'LX-350', 'ESC/P']):
                logger.info(f"Detected dot-matrix printer {job.printer_name}, using Ghostscript method")
                if self._print_pdf_ghostscript(job.pdf_file, job.printer_name, devmode_data, job.orientation):
                    success = True
                else:
                    logger.warning("Ghostscript method failed, trying native method")
                    success = True
            else:
                success = True
            
            if success:
                # Wait a moment to ensure the job was sent to Windows queue
                time.sleep(1)
                
                # Log the successful submission with correlative info if available
                correlative_info = ""
                if hasattr(job, 'correlative') or 'correlativo' in job.printer_data.lower():
                    correlative_info = f" (correlative order maintained)"
                
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now()
                logger.info(f"Successfully completed job {job.id}{seq_info} for {job.printer_name}{correlative_info}")
                
                # Additional verification: check if job appeared in Windows queue
                if not self._is_windows_printer_queue_empty():
                    logger.info(f"Job {job.id}{seq_info} successfully queued in Windows for {job.printer_name}")
                else:
                    logger.debug(f"Windows queue empty after sending job {job.id}{seq_info} - job may have processed immediately")
            else:
                raise Exception("Printing failed")
                
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()
            logger.error(f"Failed to process job {job.id}: {e}")
            
        finally:
            # Add to history and cleanup
            self.job_history.append(job)
            
            # Keep only last 50 jobs in history
            if len(self.job_history) > 50:
                self.job_history = self.job_history[-50:]
            
            self.current_job = None
            self.is_processing = False
    
    def _extract_orientation_from_devmode(self, devmode_data: bytes) -> str:
        """Extract orientation from DEVMODE data"""
        try:
            if not devmode_data or len(devmode_data) < 78:
                logger.info(f"entrando aqui")
                return 'portrait'  # Default fallback
            
            # Extract dmFields to check if orientation is set
            dm_fields = int.from_bytes(devmode_data[72:76], 'little')
            DM_ORIENTATION = 0x00000001
            
            if dm_fields & DM_ORIENTATION:
                # Extract dmOrientation (offset 76, 2 bytes)
                orientation_value = int.from_bytes(devmode_data[76:78], 'little', signed=True)
                # DMORIENT_PORTRAIT = 1, DMORIENT_LANDSCAPE = 2
                logger.info(f"o entrando aqui")
                logger.info(f"orientation{orientation_value}")
                return 'landscape' if orientation_value == 2 else 'portrait'
            
            else:
                logger.info(f"o aqui x2")
                return 'portrait'  # Default if orientation not set
                
        except Exception as e:
            logger.warning(f"Error extracting orientation from DEVMODE: {e}")
            logger.info(f"entrando al falló")
            return 'portrait'  # Safe fallback
    
    def _print_pdf_ghostscript(self, pdf_file: str, printer_name: str, devmode_data: bytes = None, orientation: str = 'portrait') -> bool:
        """Print PDF using Ghostscript/gsprint for better compatibility with dot-matrix printers"""
        try:
            import os
            import subprocess
            
            cwd = os.getcwd()
            gspath = os.path.join(cwd, "bin", "ghostscript.exe")
            gsp_path = os.path.join(cwd, "bin", "gsprint.exe")
            
            # Check if gsprint.exe exists
            if not os.path.exists(gsp_path):
                logger.error(f"gsprint.exe not found at {gsp_path}")
                return False
                
            if not os.path.exists(gspath):
                logger.error(f"ghostscript.exe not found at {gspath}")
                return False
            
            # Extract orientation from DEVMODE if available, otherwise use parameter
            actual_orientation = self._extract_orientation_from_devmode(devmode_data) if devmode_data else orientation
            logger.info(f"Using orientation: {actual_orientation} (from {'DEVMODE' if devmode_data else 'parameter'})")
            
            # Set orientation parameter
            cmd_orientation = '-landscape' if actual_orientation.lower() == 'landscape' else '-portrait'
            
            # Build gsprint command
            cmd = [
                gsp_path,
                '-ghostscript', gspath,
                cmd_orientation,
                '-printer', printer_name,
                pdf_file
            ]
            
            logger.info(f"Executing gsprint: {' '.join(cmd)}")
            
            # Execute gsprint
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully sent {pdf_file} to {printer_name} using Ghostscript")
                return True
            else:
                logger.error(f"gsprint failed with return code {result.returncode}: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Ghostscript printing failed: {e}")
            return False
    
    def _print_pdf_native(self, pdf_file: str, printer_name: str, devmode_data: bytes) -> bool:
        """Print PDF using native Windows printing API without Adobe/spooler"""
        try:
            # Convert PDF to PostScript using Ghostscript
            ps_data = self._convert_pdf_to_postscript(pdf_file)
            if not ps_data:
                logger.error("Failed to convert PDF to PostScript")
                return False
            
            # Open printer
            printer_handle = win32print.OpenPrinter(printer_name)
            
            try:
                # Apply stored DEVMODE configuration
                if devmode_data and len(devmode_data) > 0:
                    try:
                        logger.info(f"Applied stored configuration to {printer_name}")
                    except Exception as e:
                        logger.warning(f"Could not apply DEVMODE: {e}")
                
                # Start a print job
                # StartDocPrinter expects a 3-item sequence (pDocName, pOutputFile, pDatatype)
                # Use 'PostScript' datatype instead of 'RAW' for proper PostScript interpretation
                job_info = (
                    f'Print Job {self.current_job.id if self.current_job else "Unknown"}',  # pDocName
                    None,  # pOutputFile
                    'PostScript'  # pDatatype - ensures printer interprets PostScript correctly
                )
                
                print_job_id = win32print.StartDocPrinter(printer_handle, 1, job_info)
                
                if print_job_id == 0:
                    raise Exception("Failed to start print job")
                
                try:
                    # Start a page
                    win32print.StartPagePrinter(printer_handle)
                    
                    # Send PostScript data directly to printer
                    bytes_written = win32print.WritePrinter(printer_handle, ps_data)
                    
                    if bytes_written != len(ps_data):
                        logger.warning(f"Not all data written: {bytes_written}/{len(ps_data)} bytes")
                    
                    # End the page
                    win32print.EndPagePrinter(printer_handle)
                    
                    # End the document
                    win32print.EndDocPrinter(printer_handle)
                    
                    logger.info(f"PDF printed natively to {printer_name} ({bytes_written} bytes sent)")
                    return True
                    
                except Exception as e:
                    win32print.EndDocPrinter(printer_handle)
                    raise e
                    
            finally:
                win32print.ClosePrinter(printer_handle)
                
        except Exception as e:
            logger.error(f"Native printing failed: {e}")
            # Fallback to spooler method if native fails
            logger.info("Falling back to spooler method")
            return self._print_via_spooler(pdf_file, printer_name)
    
    def _convert_pdf_to_postscript(self, pdf_file: str) -> bytes:
        """Convert PDF to PostScript using Ghostscript"""
        try:
            import subprocess
            import os
            import tempfile
            import shutil
            
            # Try to find Ghostscript executable in common locations
            possible_paths = [
                # Local bin directory
                os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bin', 'ghostscript.exe'),
                # Standard Ghostscript installation paths
                'gswin64c.exe',  # Try system PATH first
                'gswin32c.exe',
                r'C:\Program Files\gs\gs*\bin\gswin64c.exe',
                r'C:\Program Files (x86)\gs\gs*\bin\gswin32c.exe'
            ]
            
            gs_path = None
            for path in possible_paths:
                if '*' in path:
                    # Handle wildcard paths
                    import glob
                    matches = glob.glob(path)
                    if matches:
                        gs_path = matches[0]
                        break
                elif shutil.which(path) or os.path.exists(path):
                    gs_path = path
                    break
            
            if not gs_path:
                logger.error("Ghostscript not found. Please install Ghostscript or ensure it's in PATH")
                return None
            
            # Create temporary PostScript file
            with tempfile.NamedTemporaryFile(suffix='.ps', delete=False) as temp_ps:
                temp_ps_path = temp_ps.name
            
            try:
                # Convert PDF to PostScript using Ghostscript (silent execution)
                cmd = [
                    gs_path,
                    '-dNOPAUSE',
                    '-dBATCH',
                    '-dSAFER',
                    '-dQUIET',  # Suppress output messages
                    '-sDEVICE=ps2write',
                    f'-sOutputFile={temp_ps_path}',
                    pdf_file
                ]
                
                # Run Ghostscript in background without showing window
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=30,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode != 0:
                    logger.error(f"Ghostscript conversion failed: {result.stderr}")
                    return None
                
                # Read the PostScript data
                with open(temp_ps_path, 'rb') as ps_file:
                    ps_data = ps_file.read()
                
                logger.info(f"PDF converted to PostScript ({len(ps_data)} bytes)")
                return ps_data
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_ps_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"PDF to PostScript conversion failed: {e}")
            return None
    
    def _print_via_spooler(self, pdf_file: str, printer_name: str) -> bool:
        """Print PDF via Windows print spooler"""
        try:
            # Set the target printer as default temporarily
            original_default = None
            try:
                original_default = win32print.GetDefaultPrinter()
            except:
                pass
            
            # Set target printer as default
            win32print.SetDefaultPrinter(printer_name)
            
            try:
                # Use Windows print command directly
                import subprocess
                import os
                
                # Method 1: Try using Windows print command
                cmd = f'powershell -Command "Start-Process -FilePath \\"{pdf_file}\\" -Verb Print -WindowStyle Hidden"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    logger.info(f"PDF sent to printer {printer_name} via PowerShell")
                    # Wait a moment for the print job to be spooled
                    time.sleep(2)
                    return True
                else:
                    logger.warning(f"PowerShell print failed: {result.stderr}")
                    
                    # Method 2: Fallback to direct file association
                    os.startfile(pdf_file, "print")
                    logger.info(f"PDF sent to printer {printer_name} via startfile")
                    time.sleep(2)
                    return True
                    
            finally:
                # Restore original default printer
                if original_default:
                    try:
                        win32print.SetDefaultPrinter(original_default)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Spooler printing failed: {e}")
            return False
    
class PrintQueueManager:
    """Manages logical print queues for all printers"""
    
    def __init__(self):
        self.printer_queues: Dict[str, PrinterQueue] = {}
        self.lock = threading.Lock()
        self._initialize_printer_queues()
    
    def _initialize_printer_queues(self):
        """Initialize queues for all available printers (local, shared, and network)"""
        try:
            all_printers = self._get_all_available_printers()
            
            with self.lock:
                for printer_info in all_printers:
                    printer_name = printer_info['name']
                    if printer_name not in self.printer_queues:
                        queue = PrinterQueue(printer_name)
                        queue.printer_type = printer_info['type']  # Store printer type
                        self.printer_queues[printer_name] = queue
            
            logger.info(f"Initialized queues for {len(all_printers)} printers (local, shared, and network)")
            
        except Exception as e:
            logger.error(f"Error initializing printer queues: {e}")
    
    def _get_all_available_printers(self):
        """Get all available printers including local, shared, and network printers"""
        all_printers = []
        
        try:
            # Get local printers (PRINTER_ENUM_LOCAL = 2)
            local_printers = win32print.EnumPrinters(2)
            for printer in local_printers:
                all_printers.append({
                    'name': printer[2],
                    'type': 'local',
                    'server': '',
                    'comment': printer[1] if len(printer) > 1 else ''
                })
            
            # Get network connections (PRINTER_ENUM_CONNECTIONS = 32)
            try:
                network_connections = win32print.EnumPrinters(32)
                for printer in network_connections:
                    all_printers.append({
                        'name': printer[2],
                        'type': 'network_connection',
                        'server': printer[4] if len(printer) > 4 else '',
                        'comment': printer[1] if len(printer) > 1 else ''
                    })
            except Exception as e:
                logger.debug(f"No network connections found or error accessing them: {e}")
            
            # Get shared printers (PRINTER_ENUM_LOCAL | PRINTER_ENUM_SHARED = 2 | 4 = 6)
            try:
                shared_printers = win32print.EnumPrinters(6)
                for printer in shared_printers:
                    # Check if this printer is already in our list (avoid duplicates)
                    if not any(p['name'] == printer[2] for p in all_printers):
                        all_printers.append({
                            'name': printer[2],
                            'type': 'shared',
                            'server': '',
                            'comment': printer[1] if len(printer) > 1 else ''
                        })
            except Exception as e:
                logger.debug(f"No shared printers found or error accessing them: {e}")
            
            logger.info(f"Found {len(all_printers)} total printers")
            for printer in all_printers:
                logger.debug(f"Printer: {printer['name']} (Type: {printer['type']})")
                
        except Exception as e:
            logger.error(f"Error getting all available printers: {e}")
            # Fallback to original method
            try:
                printers = win32print.EnumPrinters(2)
                all_printers = [{
                    'name': printer[2],
                    'type': 'local',
                    'server': '',
                    'comment': printer[1] if len(printer) > 1 else ''
                } for printer in printers]
            except Exception as fallback_error:
                logger.error(f"Fallback printer enumeration also failed: {fallback_error}")
        
        return all_printers
    
    def refresh_printer_queues(self):
        """Refresh printer queues (add new printers, remove unavailable ones)"""
        try:
            # Get all available printers (local, network, and shared)
            all_printers = self._get_all_available_printers()
            current_printers = set(printer_info['name'] for printer_info in all_printers)
            
            with self.lock:
                # Add new printers
                for printer_info in all_printers:
                    printer_name = printer_info['name']
                    if printer_name not in self.printer_queues:
                        queue = PrinterQueue(printer_name)
                        queue.printer_type = printer_info['type']  # Store printer type
                        self.printer_queues[printer_name] = queue
                        logger.info(f"Added queue for new {printer_info['type']} printer: {printer_name}")
                
                # Remove unavailable printers
                unavailable_printers = set(self.printer_queues.keys()) - current_printers
                for printer_name in unavailable_printers:
                    queue = self.printer_queues.pop(printer_name)
                    queue.stop_worker()
                    logger.info(f"Removed queue for unavailable printer: {printer_name}")
            
        except Exception as e:
            logger.error(f"Error refreshing printer queues: {e}")
    
    def submit_print_job(self, printer_name: str, printer_data: str, orientation: str) -> Optional[str]:
        """
        Submit a print job to the appropriate queue.
        
        Args:
            printer_name: Name of the target printer
            printer_data: HTML/data to print
            orientation: "portrait" or "landscape"
            
        Returns:
            Job ID if successful, None otherwise
        """
        try:
            # Validate printer exists
            if printer_name not in self.printer_queues:
                self.refresh_printer_queues()
                
            if printer_name not in self.printer_queues:
                logger.error(f"Printer not found: {printer_name}")
                return None
            
            # Check if configuration exists
            if not printer_config_store.is_configured(printer_name, orientation.lower()):
                logger.error(f"Printer {printer_name} not configured for {orientation}")
                raise Exception(f"Printer {printer_name} is not configured for {orientation} orientation. "
                              f"Please configure it in the Print Queue Manager.")
            
            # Create print job
            job = PrintJob(
                printer_name=printer_name,
                printer_data=printer_data,
                orientation=orientation.lower()
            )
            
            # Extract correlative info for logging if available
            correlative_info = ""
            try:
                if "correlativo" in printer_data.lower():
                    import re
                    correlative_match = re.search(r'correlativo["\s]*:?\s*["\s]*([^"<>\s]+)', printer_data, re.IGNORECASE)
                    if correlative_match:
                        correlative_info = f" [Correlativo: {correlative_match.group(1)}]"
            except:
                pass  # Ignore errors in correlative extraction
            
            logger.info(f"Received print job for {printer_name}{correlative_info} - assigning to queue")
            
            # Submit to queue
            queue = self.printer_queues[printer_name]
            success = queue.add_job(job)
            
            if success:
                seq_info = f" (seq #{job.sequence_number})" if job.sequence_number else ""
                logger.info(f"Successfully submitted print job {job.id}{seq_info} to {printer_name}{correlative_info}")
                return job.id
            else:
                logger.error(f"Failed to submit print job to {printer_name}{correlative_info}")
                return None
                
        except Exception as e:
            logger.error(f"Error submitting print job: {e}")
            raise
    
    def get_all_queue_status(self) -> Dict[str, Any]:
        """Get status of all printer queues"""
        try:
            with self.lock:
                return {
                    printer_name: queue.get_queue_status()
                    for printer_name, queue in self.printer_queues.items()
                }
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return {}
    
    def get_printer_queue_status(self, printer_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific printer queue"""
        try:
            with self.lock:
                if printer_name in self.printer_queues:
                    return self.printer_queues[printer_name].get_queue_status()
                return None
        except Exception as e:
            logger.error(f"Error getting printer queue status: {e}")
            return None
    
    def get_available_printers(self) -> List[str]:
        """Get list of available printers"""
        try:
            with self.lock:
                return list(self.printer_queues.keys())
        except Exception as e:
            logger.error(f"Error getting available printers: {e}")
            return []
    
    def get_available_printers_with_info(self) -> List[Dict[str, str]]:
        """Get list of available printers with their type information"""
        try:
            with self.lock:
                return [
                    {
                        'name': printer_name,
                        'type': queue.printer_type
                    }
                    for printer_name, queue in self.printer_queues.items()
                ]
        except Exception as e:
            logger.error(f"Error getting available printers with info: {e}")
            return []
    
    def shutdown(self):
        """Shutdown all printer queues"""
        try:
            with self.lock:
                for queue in self.printer_queues.values():
                    queue.stop_worker()
                
                self.printer_queues.clear()
                
            logger.info("Print queue manager shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# Global instance
print_queue_manager = PrintQueueManager()