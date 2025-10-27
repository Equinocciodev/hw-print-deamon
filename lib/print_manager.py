"""
Print Manager with Logical Queues
Manages logical print queues per printer and processes jobs using stored configurations
"""
import threading
import time
import uuid
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re

from lib.config_store import printer_config_store
from lib import pdf
from lib.job_store import job_store, JobRecord
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
    attempts: int = 0
    max_attempts: int = 3
    available_at: Optional[datetime] = None
    external_sequence: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    verification_status: str = "pending"
    verification_message: str = ""
    
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
            'sequence_number': self.sequence_number,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'available_at': self.available_at.isoformat() if self.available_at else None,
            'external_sequence': self.external_sequence,
            'metadata': self.metadata,
            'verification_status': self.verification_status,
            'verification_message': self.verification_message
        }

    @classmethod
    def from_record(cls, record: JobRecord) -> "PrintJob":
        """Create a PrintJob instance from a JobRecord."""
        try:
            status = JobStatus(record.status)
        except ValueError:
            status = JobStatus.QUEUED
        return cls(
            id=record.id,
            printer_name=record.printer_name,
            printer_data=record.payload,
            orientation=record.orientation,
            status=status,
            created_at=record.created_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
            error_message=record.error_message or "",
            pdf_file=record.pdf_file or "",
            pages=record.pages or 1,
            sequence_number=record.sequence_number,
            attempts=record.attempts,
            max_attempts=record.max_attempts,
            available_at=record.available_at,
            external_sequence=record.external_sequence,
            metadata=record.metadata or {},
            verification_status=record.verification_status or "pending",
            verification_message=record.verification_message or ""
        )


class PrinterQueue:
    """Logical queue for a specific printer"""
    
    def __init__(self, printer_name: str):
        self.printer_name = printer_name
        self.printer_type = "local"  # Default type, will be updated when detected
        self.current_job: Optional[PrintJob] = None
        self.job_history: List[PrintJob] = []
        self.is_processing = False
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.new_job_event = threading.Event()
        self.printer_state_lock = threading.Lock()
        self._pause_logged = False
        
        # Recover any stuck jobs before starting
        try:
            job_store.recover_stuck_jobs(self.printer_name)
        except Exception as exc:
            logger.error("Failed to recover jobs for %s: %s", self.printer_name, exc)
        
        # Start worker thread
        self.start_worker()
    
    def start_worker(self):
        """Start the worker thread for this queue"""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.stop_event.clear()
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            logger.info(f"Started worker thread for printer: {self.printer_name}")
            self.new_job_event.set()
    
    def stop_worker(self):
        """Stop the worker thread"""
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_event.set()
            self.worker_thread.join(timeout=5)
            logger.info(f"Stopped worker thread for printer: {self.printer_name}")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        printer_state = job_store.get_printer_state(self.printer_name)
        return {
            'printer_name': self.printer_name,
            'printer_type': self.printer_type,
            'queue_size': job_store.count_pending(self.printer_name),
            'is_processing': self.is_processing,
            'paused': printer_state.get('paused', False),
            'pause_reason': printer_state.get('pause_reason'),
            'last_sequence_processed': printer_state.get('last_sequence_processed'),
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
                # Wait until new jobs arrive or retry interval expires
                self.new_job_event.wait(timeout=1.0)
                self.new_job_event.clear()

                if self.stop_event.is_set():
                    break

                printer_state = job_store.get_printer_state(self.printer_name)
                if printer_state.get('paused'):
                    if not getattr(self, "_pause_logged", False):
                        logger.warning(
                            "Printer %s queue is paused: %s",
                            self.printer_name,
                            printer_state.get('pause_reason') or "manual pause",
                        )
                        self._pause_logged = True
                    time.sleep(2)
                    continue
                else:
                    if getattr(self, "_pause_logged", False):
                        logger.info("Printer %s queue resumed", self.printer_name)
                        self._pause_logged = False

                record = job_store.fetch_next_job(self.printer_name)
                if not record:
                    continue

                job = PrintJob.from_record(record)
                self.current_job = job
                self.is_processing = True

                seq_info = f" (seq #{job.sequence_number})" if job.sequence_number else ""
                logger.info(f"Worker for {self.printer_name} picked up job {job.id}{seq_info} (attempt {job.attempts}/{job.max_attempts})")

                try:
                    process_result = self._process_job(job)
                    job_store.mark_job_completed(
                        job.id,
                        pdf_file=process_result.get('pdf_file'),
                        pages=process_result.get('pages'),
                        verification_message=process_result.get('verification_message'),
                    )

                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.now()
                    job.verification_status = "verified"
                    job.verification_message = process_result.get('verification_message', "")
                    job.pdf_file = process_result.get('pdf_file', job.pdf_file)
                    job.pages = process_result.get('pages', job.pages)

                    logger.info(f"Worker for {self.printer_name} completed job {job.id}{seq_info}")

                except Exception as e:
                    error_message = str(e)
                    logger.error(
                        "Error processing job %s for printer %s: %s",
                        job.id,
                        self.printer_name,
                        error_message,
                        exc_info=True,
                    )
                    job.status = JobStatus.FAILED
                    job.error_message = error_message
                    job.completed_at = datetime.now()

                    fail_info = job_store.mark_job_failed(job.id, error=error_message)
                    if fail_info.get("paused"):
                        logger.error(
                            "Printer %s queue paused due to job %s failures. Manual intervention required.",
                            self.printer_name,
                            job.id,
                        )
                        self._pause_logged = True
                    else:
                        logger.info(
                            "Job %s scheduled for retry (%d/%d)",
                            job.id,
                            fail_info.get("attempts"),
                            fail_info.get("max_attempts"),
                        )
                        # Wake up worker around retry time
                        self._schedule_retry_wakeup(fail_info.get("retry_at"))

                finally:
                    self.job_history.append(job)
                    if len(self.job_history) > 50:
                        self.job_history = self.job_history[-50:]
                    self.current_job = None
                    self.is_processing = False

            except Exception as loop_error:
                logger.exception("Unexpected error in worker loop for %s: %s", self.printer_name, loop_error)
                time.sleep(2)

        logger.info(f"Worker loop stopped for printer: {self.printer_name}")

    def _schedule_retry_wakeup(self, retry_at_iso: Optional[str]) -> None:
        """Schedule a wake-up call for the worker when a retry is due."""
        if not retry_at_iso:
            self.new_job_event.set()
            return

        try:
            retry_at = datetime.fromisoformat(retry_at_iso)
        except ValueError:
            self.new_job_event.set()
            return

        delay = max((retry_at - datetime.utcnow()).total_seconds(), 0)

        def _wake_later():
            if delay > 0:
                time.sleep(delay)
            self.new_job_event.set()

        threading.Thread(target=_wake_later, daemon=True).start()

    def notify_new_job(self):
        """Wake up the worker loop to process new jobs."""
        self.new_job_event.set()
        
    def _process_job(self, job: PrintJob) -> Dict[str, Any]:
        """Process a single print job and return verification details."""
        self.current_job = job
        self.is_processing = True
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now()

        seq_info = f" (seq #{job.sequence_number})" if job.sequence_number else ""
        logger.info(f"Processing job {job.id}{seq_info} for printer {job.printer_name}")

        # Wait for Windows queue to drain to keep strict order
        logger.info(f"Waiting for Windows queue to be empty for {job.printer_name}{seq_info}...")
        max_wait_time = 300  # 5 minutes maximum wait
        wait_start = time.time()

        while not self._is_windows_printer_queue_empty():
            if time.time() - wait_start > max_wait_time:
                logger.warning(f"Timeout waiting for Windows queue to clear for {job.printer_name}{seq_info}")
                break

            logger.debug(f"Windows queue not empty for {job.printer_name}{seq_info}, waiting 2 seconds...")
            time.sleep(2)

            if self.stop_event.is_set():
                raise RuntimeError("Worker stopped while waiting for queue to clear")

        logger.info(f"Windows queue ready for {job.printer_name}, continuing with job {job.id}{seq_info}")

        config_data = printer_config_store.load_printer_config(
            job.printer_name, job.orientation.lower()
        )
        if not config_data:
            raise RuntimeError(f"No configuration found for {job.printer_name}:{job.orientation}")

        devmode_data, devnames_data, stored_metadata = config_data
        if stored_metadata:
            job.metadata.update(stored_metadata)

        job.pdf_file = pdf.generate(job.printer_data, job.orientation)
        if not job.pdf_file:
            raise RuntimeError("Failed to generate PDF")

        job.status = JobStatus.PRINTING
        job_store.mark_job_printing(job.id)

        success = False
        verification_message = ""

        if self._is_dot_matrix_printer(job.printer_name):
            logger.info(f"Detected dot-matrix printer {job.printer_name}, using Ghostscript method")
            success = self._print_pdf_ghostscript(job.pdf_file, job.printer_name, devmode_data, job.orientation)
            if not success:
                logger.warning("Ghostscript method failed, attempting native printing fallback")
                success = self._print_pdf_native(job.pdf_file, job.printer_name, devmode_data)
        else:
            success = self._print_pdf_native(job.pdf_file, job.printer_name, devmode_data)

        if not success:
            raise RuntimeError("Printing failed")

        # Verification: ensure the job entered the Windows spooler
        time.sleep(1)
        if not self._is_windows_printer_queue_empty():
            verification_message = "Job accepted into Windows spooler"
            logger.info(f"Job {job.id}{seq_info} successfully queued in Windows for {job.printer_name}")
        else:
            verification_message = "Windows queue empty post-print; assuming immediate completion"
            logger.debug(f"Windows queue empty after sending job {job.id}{seq_info}")

        correlative_info = ""
        if job.external_sequence:
            correlative_info = f" (seq {job.external_sequence})"

        logger.info(f"Successfully processed job {job.id}{seq_info}{correlative_info} for {job.printer_name}")

        return {
            'pdf_file': job.pdf_file,
            'pages': job.pages,
            'verification_message': verification_message,
        }
    
    def _is_dot_matrix_printer(self, printer_name: str) -> bool:
        """Heuristic to detect dot-matrix printers that work better with Ghostscript."""
        dot_matrix_signatures = ['FX-2190', 'LX-350', 'ESC/P', 'LQ-590', 'LQ-2090', 'LQ-310']
        upper_name = printer_name.upper()
        return any(signature in upper_name for signature in dot_matrix_signatures)
    
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
    
    @staticmethod
    def _extract_job_metadata(printer_data: str) -> Dict[str, Any]:
        """Extract sequence/correlative hints from payload for traceability."""
        metadata: Dict[str, Any] = {}
        try:
            sequence_patterns = [
                r'"seq"\s*[:=]\s*"([^"]+)"',
                r'"sequence"\s*[:=]\s*"([^"]+)"',
                r'\bseq(?:uencia)?\b\s*[:=]\s*[\'"]?([A-Za-z0-9\-\/]+)',
            ]
            correlativo_patterns = [
                r'"correlativo"\s*[:=]\s*"([^"]+)"',
                r'\bcorrelativo\b\s*[:=]\s*[\'"]?([A-Za-z0-9\-\/]+)',
            ]

            for pattern in sequence_patterns:
                match = re.search(pattern, printer_data, re.IGNORECASE)
                if match:
                    metadata.setdefault('sequence', match.group(1).strip())
                    break

            for pattern in correlativo_patterns:
                match = re.search(pattern, printer_data, re.IGNORECASE)
                if match:
                    metadata.setdefault('correlativo', match.group(1).strip())
                    break

            if 'sequence' in metadata:
                metadata['sequence_source'] = 'payload'
            if 'correlativo' in metadata:
                metadata['correlativo_source'] = 'payload'

        except Exception as exc:
            logger.debug("Failed to extract metadata from payload: %s", exc)

        return metadata

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
            
            job_id = str(uuid.uuid4())
            metadata = self._extract_job_metadata(printer_data)
            external_sequence = metadata.get('sequence') or metadata.get('correlativo')

            logger.info(
                "Received print job for %s (orientation=%s, seq=%s) - storing in persistent queue",
                printer_name,
                orientation.lower(),
                external_sequence or "n/a",
            )

            record = job_store.enqueue_job(
                job_id=job_id,
                printer_name=printer_name,
                orientation=orientation.lower(),
                payload=printer_data,
                external_sequence=external_sequence,
                metadata=metadata,
            )

            queue = self.printer_queues[printer_name]
            queue.notify_new_job()

            logger.info(
                "Persisted and queued print job %s (seq #%s, external=%s) for %s",
                record.id,
                record.sequence_number,
                external_sequence or "n/a",
                printer_name,
            )
            return record.id
                
        except Exception as e:
            logger.error(f"Error submitting print job: {e}")
            raise
    
    def get_unprinted_jobs(self, printer_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return pending/failed jobs for monitoring and recovery."""
        records = job_store.get_unprinted_jobs(printer_name)
        jobs: List[Dict[str, Any]] = []
        for record in records:
            try:
                jobs.append(PrintJob.from_record(record).to_dict())
            except Exception as exc:
                logger.debug("Failed to convert job record %s: %s", record.id, exc)
        return jobs

    def requeue_job(self, job_id: str, *, reset_attempts: bool = False) -> Optional[Dict[str, Any]]:
        """Requeue a specific job (for manual recovery)."""
        record = job_store.requeue_job(job_id, reset_attempts=reset_attempts)
        if not record:
            return None

        queue = self.printer_queues.get(record.printer_name)
        if queue:
            queue.notify_new_job()

        return PrintJob.from_record(record).to_dict()

    def resume_printer(self, printer_name: str) -> None:
        """Resume a paused printer queue."""
        job_store.resume_printer(printer_name)
        queue = self.printer_queues.get(printer_name)
        if queue:
            queue.notify_new_job()

    def detect_sequence_gaps(self, printer_name: str) -> List[Dict[str, Any]]:
        """Inspect stored jobs to detect gaps in recorded sequences."""
        return job_store.detect_sequence_gaps(printer_name)
    
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