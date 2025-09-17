"""
Print Queue Manager GUI
PyQt interface for managing printer configurations and print queues
"""
import sys
import logging
from typing import Dict, List, Optional
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTableWidget, QTableWidgetItem, 
                            QPushButton, QLabel, QMessageBox, QTabWidget,
                            QTextEdit, QSplitter, QHeaderView, QProgressBar,
                            QStatusBar, QGroupBox, QLineEdit, QComboBox,
                            QFormLayout, QSpinBox, QDoubleSpinBox)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QFont
import win32print
import win32gui

from lib.config_store import printer_config_store, PDFOrientationConfigStore
from lib.win32_printdlgex import win32_print_wrapper
from lib.alternative_printer_config import alternative_printer_config

logger = logging.getLogger(__name__)


class PrinterConfigThread(QThread):
    """Thread for handling printer configuration dialogs"""
    config_saved = pyqtSignal(str, str, dict)  # printer_name, orientation, metadata
    error_occurred = pyqtSignal(str)
    
    def __init__(self, hwnd_owner: int, printer_name: str, orientation: str):
        super().__init__()
        self.hwnd_owner = hwnd_owner
        self.printer_name = printer_name
        self.orientation = orientation
    
    def run(self):
        """Run the configuration dialog in a separate thread"""
        try:
            # Load existing configuration if available
            existing_config = printer_config_store.load_printer_config(
                self.printer_name, self.orientation)
            
            existing_devmode = None
            existing_devnames = None
            
            if existing_config:
                existing_devmode, existing_devnames, _ = existing_config
            
            # Try the native Windows print properties dialog first
            result = win32_print_wrapper.show_print_properties_dialog(
                self.hwnd_owner,
                self.printer_name,
                existing_devmode,
                existing_devnames
            )
            
            # If PrintDlgEx fails, try the alternative DocumentProperties approach
            if not result:
                logger.warning(f"PrintDlgEx failed for {self.printer_name}, trying DocumentProperties")
                
                alternative_result = alternative_printer_config.show_printer_properties_dialog(
                    self.hwnd_owner,
                    self.printer_name,
                    existing_devmode
                )
                
                if alternative_result:
                    devmode_data, metadata = alternative_result
                    # Create empty devnames since DocumentProperties doesn't provide it
                    devnames_data = b'\x00' * 64  # Minimum DEVNAMES size
                    result = (devmode_data, devnames_data, metadata)
            
            if result:
                devmode_data, devnames_data, metadata = result
                
                # Save the configuration
                success = printer_config_store.save_printer_config(
                    self.printer_name,
                    self.orientation,
                    devmode_data,
                    devnames_data,
                    metadata.get('paper_size', ''),
                    metadata.get('duplex', ''),
                    metadata.get('color', ''),
                    str(metadata.get('tray', ''))
                )
                
                if success:
                    self.config_saved.emit(self.printer_name, self.orientation, metadata)
                else:
                    self.error_occurred.emit("Failed to save printer configuration")
            else:
                self.error_occurred.emit("User cancelled configuration or dialog failed")
            
        except Exception as e:
            logger.error(f"Error in printer configuration thread: {e}")
            self.error_occurred.emit(f"Configuration error: {str(e)}")


class PrintQueueWidget(QWidget):
    """Widget for displaying print queue status"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
        # Timer for updating queue status
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_queue_status)
        self.update_timer.start(2000)  # Update every 2 seconds
    
    def init_ui(self):
        """Initialize the print queue UI"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Print Queue Status")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Queue table
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(6)
        self.queue_table.setHorizontalHeaderLabels([
            "Printer", "Job ID", "Document", "Status", "Pages", "Size"
        ])
        
        # Make table stretch to fit
        header = self.queue_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.queue_table)
        
        # Status info
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def update_queue_status(self):
        """Update the print queue status"""
        try:
            # Get print jobs from Windows spooler
            jobs = []
            printers = [printer[2] for printer in win32print.EnumPrinters(2)]
            
            for printer_name in printers:
                try:
                    printer_handle = win32print.OpenPrinter(printer_name)
                    printer_jobs = win32print.EnumJobs(printer_handle, 0, -1, 1)
                    
                    for job in printer_jobs:
                        # Some printers (like ZDesigner) may not have 'Size' property
                        size_value = job.get('Size', 0)
                        jobs.append({
                            'printer': printer_name,
                            'job_id': job['JobId'],
                            'document': job['pDocument'],
                            'status': self._get_job_status_text(job['Status']),
                            'pages': job['TotalPages'],
                            'size': f"{size_value} bytes"
                        })
                    
                    win32print.ClosePrinter(printer_handle)
                    
                except Exception as e:
                    logger.error(f"Error getting jobs for printer {printer_name}: {e}")
            
            # Update table
            self.queue_table.setRowCount(len(jobs))
            
            for row, job in enumerate(jobs):
                self.queue_table.setItem(row, 0, QTableWidgetItem(job['printer']))
                self.queue_table.setItem(row, 1, QTableWidgetItem(str(job['job_id'])))
                self.queue_table.setItem(row, 2, QTableWidgetItem(job['document']))
                self.queue_table.setItem(row, 3, QTableWidgetItem(job['status']))
                self.queue_table.setItem(row, 4, QTableWidgetItem(str(job['pages'])))
                self.queue_table.setItem(row, 5, QTableWidgetItem(job['size']))
            
            # Update status
            self.status_label.setText(f"Active jobs: {len(jobs)}")
            
        except Exception as e:
            logger.error(f"Error updating queue status: {e}")
            self.status_label.setText("Error updating queue status")
    
    def _get_job_status_text(self, status: int) -> str:
        """Convert job status to readable text"""
        if status == 0:
            return "Queued"
        elif status & 0x01:
            return "Paused"
        elif status & 0x02:
            return "Error"
        elif status & 0x04:
            return "Deleting"
        elif status & 0x08:
            return "Spooling"
        elif status & 0x10:
            return "Printing"
        elif status & 0x20:
            return "Offline"
        elif status & 0x40:
            return "Out of Paper"
        else:
            return "Unknown"


class PrinterConfigWidget(QWidget):
    """Widget for configuring printers"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config_thread = None
        self.init_ui()
        self.refresh_printers()
    
    def init_ui(self):
        """Initialize the printer configuration UI"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Printer Configuration")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Printers")
        refresh_btn.clicked.connect(self.refresh_printers)
        layout.addWidget(refresh_btn)
        
        # Printers table
        self.printers_table = QTableWidget()
        self.printers_table.setColumnCount(8)
        self.printers_table.setHorizontalHeaderLabels([
            "Printer Name", "Portrait", "Portrait Config", "Landscape", 
            "Landscape Config", "Configure Portrait", "Configure Landscape", "Status"
        ])
        
        # Make some columns stretch
        header = self.printers_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Printer name
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)  # Status
        
        layout.addWidget(self.printers_table)
        
        # Status
        self.config_status = QLabel("Ready")
        layout.addWidget(self.config_status)
        
        self.setLayout(layout)
    
    def refresh_printers(self):
        """Refresh the list of available printers"""
        try:
            # Get list of printers from Windows
            printers = [printer[2] for printer in win32print.EnumPrinters(2)]
            
            # Get configurations for all printers
            all_configs = printer_config_store.get_all_configurations()
            
            # Update table
            self.printers_table.setRowCount(len(printers))
            
            for row, printer_name in enumerate(printers):
                # Printer name
                self.printers_table.setItem(row, 0, QTableWidgetItem(printer_name))
                
                # Get configurations for this printer
                printer_configs = all_configs.get(printer_name, {})
                portrait_config = printer_configs.get('portrait', {})
                landscape_config = printer_configs.get('landscape', {})
                
                # Portrait status
                portrait_configured = portrait_config.get('is_configured', False)
                self.printers_table.setItem(row, 1, QTableWidgetItem(
                    "✓" if portrait_configured else "✗"))
                
                # Portrait configuration details
                portrait_details = ""
                if portrait_configured:
                    portrait_details = f"{portrait_config.get('paper_size', 'N/A')} | {portrait_config.get('color', 'N/A')}"
                self.printers_table.setItem(row, 2, QTableWidgetItem(portrait_details))
                
                # Landscape status
                landscape_configured = landscape_config.get('is_configured', False)
                self.printers_table.setItem(row, 3, QTableWidgetItem(
                    "✓" if landscape_configured else "✗"))
                
                # Landscape configuration details
                landscape_details = ""
                if landscape_configured:
                    landscape_details = f"{landscape_config.get('paper_size', 'N/A')} | {landscape_config.get('color', 'N/A')}"
                self.printers_table.setItem(row, 4, QTableWidgetItem(landscape_details))
                
                # Configure Portrait button
                portrait_btn = QPushButton("Configure")
                portrait_btn.clicked.connect(
                    lambda checked, pname=printer_name: self.configure_printer(pname, "portrait"))
                self.printers_table.setCellWidget(row, 5, portrait_btn)
                
                # Configure Landscape button
                landscape_btn = QPushButton("Configure")
                landscape_btn.clicked.connect(
                    lambda checked, pname=printer_name: self.configure_printer(pname, "landscape"))
                self.printers_table.setCellWidget(row, 6, landscape_btn)
                
                # Overall status
                status = "Ready"
                if not portrait_configured and not landscape_configured:
                    status = "Not Configured"
                elif not portrait_configured or not landscape_configured:
                    status = "Partially Configured"
                else:
                    status = "Fully Configured"
                
                self.printers_table.setItem(row, 7, QTableWidgetItem(status))
            
            self.config_status.setText(f"Found {len(printers)} printers")
            logger.info(f"Refreshed printer list: {len(printers)} printers found")
            
        except Exception as e:
            logger.error(f"Error refreshing printers: {e}")
            self.config_status.setText(f"Error: {str(e)}")
    
    def configure_printer(self, printer_name: str, orientation: str):
        """Configure a printer for a specific orientation"""
        try:
            if self.config_thread and self.config_thread.isRunning():
                QMessageBox.warning(self, "Configuration in Progress", 
                                  "Please wait for the current configuration to complete.")
                return
            
            # Get the window handle
            hwnd = int(self.parent_window.winId()) if self.parent_window else 0
            
            self.config_status.setText(f"Configuring {printer_name} ({orientation})...")
            
            # Create and start configuration thread
            self.config_thread = PrinterConfigThread(hwnd, printer_name, orientation)
            self.config_thread.config_saved.connect(self.on_config_saved)
            self.config_thread.error_occurred.connect(self.on_config_error)
            self.config_thread.start()
            
        except Exception as e:
            logger.error(f"Error starting printer configuration: {e}")
            QMessageBox.critical(self, "Configuration Error", f"Failed to start configuration: {str(e)}")
    
    def on_config_saved(self, printer_name: str, orientation: str, metadata: dict):
        """Handle successful configuration save"""
        try:
            self.config_status.setText(f"Configuration saved for {printer_name} ({orientation})")
            
            # Show success message with details
            details = f"Paper: {metadata.get('paper_size', 'N/A')}\n"
            details += f"Color: {metadata.get('color', 'N/A')}\n"
            details += f"Duplex: {metadata.get('duplex', 'N/A')}\n"
            details += f"Orientation: {metadata.get('orientation', 'N/A')}"
            
            QMessageBox.information(self, "Configuration Saved", 
                                  f"Configuration saved successfully for:\n{printer_name} ({orientation})\n\n{details}")
            
            # Refresh the table
            self.refresh_printers()
            
        except Exception as e:
            logger.error(f"Error handling config save: {e}")
    
    def on_config_error(self, error_message: str):
        """Handle configuration error"""
        self.config_status.setText("Configuration failed")
        QMessageBox.critical(self, "Configuration Error", f"Configuration failed:\n{error_message}")


class LogWidget(QWidget):
    """Widget for displaying application logs"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize the log UI"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Application Logs")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Clear button
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_logs)
        layout.addWidget(clear_btn)
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Courier New", 9))
        layout.addWidget(self.log_display)
        
        self.setLayout(layout)
    
    def append_log(self, message: str):
        """Append a log message"""
        self.log_display.append(message)
        
        # Scroll to bottom
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_logs(self):
        """Clear all log messages"""
        self.log_display.clear()


class PDFConfigWidget(QWidget):
    """Widget for configuring PDF parameters by orientation"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf_config_store = PDFOrientationConfigStore()
        self.init_ui()
        self.load_current_configs()
    
    def init_ui(self):
        """Initialize the PDF configuration UI"""
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("Configuración de Parámetros PDF")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # Create horizontal layout for orientation configs
        orientations_layout = QHBoxLayout()
        
        # Landscape configuration
        landscape_group = QGroupBox("Configuración Horizontal (Landscape)")
        landscape_layout = QFormLayout()
        
        self.landscape_margin_top = QLineEdit()
        self.landscape_margin_right = QLineEdit()
        self.landscape_margin_bottom = QLineEdit()
        self.landscape_margin_left = QLineEdit()
        self.landscape_font_size = QLineEdit()
        self.landscape_font_family = QLineEdit()
        self.landscape_top = QLineEdit()
        
        landscape_layout.addRow("Margen Superior:", self.landscape_margin_top)
        landscape_layout.addRow("Margen Derecho:", self.landscape_margin_right)
        landscape_layout.addRow("Margen Inferior:", self.landscape_margin_bottom)
        landscape_layout.addRow("Margen Izquierdo:", self.landscape_margin_left)
        landscape_layout.addRow("Tamaño de Fuente:", self.landscape_font_size)
        landscape_layout.addRow("Familia de Fuente:", self.landscape_font_family)
        landscape_layout.addRow("Posición Vertical (top):", self.landscape_top)
        
        landscape_group.setLayout(landscape_layout)
        orientations_layout.addWidget(landscape_group)
        
        # Portrait configuration
        portrait_group = QGroupBox("Configuración Vertical (Portrait)")
        portrait_layout = QFormLayout()
        
        self.portrait_margin_top = QLineEdit()
        self.portrait_margin_right = QLineEdit()
        self.portrait_margin_bottom = QLineEdit()
        self.portrait_margin_left = QLineEdit()
        self.portrait_font_size = QLineEdit()
        self.portrait_font_family = QLineEdit()
        self.portrait_top = QLineEdit()
        
        portrait_layout.addRow("Margen Superior:", self.portrait_margin_top)
        portrait_layout.addRow("Margen Derecho:", self.portrait_margin_right)
        portrait_layout.addRow("Margen Inferior:", self.portrait_margin_bottom)
        portrait_layout.addRow("Margen Izquierdo:", self.portrait_margin_left)
        portrait_layout.addRow("Tamaño de Fuente:", self.portrait_font_size)
        portrait_layout.addRow("Familia de Fuente:", self.portrait_font_family)
        portrait_layout.addRow("Posición Vertical (top):", self.portrait_top)
        
        portrait_group.setLayout(portrait_layout)
        orientations_layout.addWidget(portrait_group)
        
        layout.addLayout(orientations_layout)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        save_button = QPushButton("Guardar Configuración")
        save_button.clicked.connect(self.save_configs)
        buttons_layout.addWidget(save_button)
        
        reset_button = QPushButton("Restaurar Valores por Defecto")
        reset_button.clicked.connect(self.reset_to_defaults)
        buttons_layout.addWidget(reset_button)
        
        test_button = QPushButton("Probar Configuración")
        test_button.clicked.connect(self.test_config)
        buttons_layout.addWidget(test_button)
        
        layout.addLayout(buttons_layout)
        
        # Status label
        self.status_label = QLabel("Listo para configurar")
        self.status_label.setStyleSheet("color: blue; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def load_current_configs(self):
        """Load current configurations into the UI"""
        try:
            # Load landscape config
            landscape_config = self.pdf_config_store.get_orientation_config('landscape')
            self.landscape_margin_top.setText(landscape_config.get('margin_top', '0in'))
            self.landscape_margin_right.setText(landscape_config.get('margin_right', '0.78in'))
            self.landscape_margin_bottom.setText(landscape_config.get('margin_bottom', '0in'))
            self.landscape_margin_left.setText(landscape_config.get('margin_left', '0.4in'))
            self.landscape_font_size.setText(landscape_config.get('font_size', '13px'))
            self.landscape_font_family.setText(landscape_config.get('font_family', "'Courier New', Courier, monospace"))
            self.landscape_top.setText(landscape_config.get('top', '0px'))
            
            # Load portrait config
            portrait_config = self.pdf_config_store.get_orientation_config('portrait')
            self.portrait_margin_top.setText(portrait_config.get('margin_top', '0in'))
            self.portrait_margin_right.setText(portrait_config.get('margin_right', '0.3in'))
            self.portrait_margin_bottom.setText(portrait_config.get('margin_bottom', '0in'))
            self.portrait_margin_left.setText(portrait_config.get('margin_left', '0.3in'))
            self.portrait_font_size.setText(portrait_config.get('font_size', '17px'))
            self.portrait_font_family.setText(portrait_config.get('font_family', "'Calibri', sans-serif"))
            self.portrait_top.setText(portrait_config.get('top', '0px'))
            
            self.status_label.setText("Configuración cargada exitosamente")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            
        except Exception as e:
            self.status_label.setText(f"Error cargando configuración: {str(e)}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            logger.error(f"Error loading PDF configs: {e}")
    
    def save_configs(self):
        """Save current configurations"""
        try:
            # Save landscape config
            landscape_config = {
                'margin_top': self.landscape_margin_top.text().strip(),
                'margin_right': self.landscape_margin_right.text().strip(),
                'margin_bottom': self.landscape_margin_bottom.text().strip(),
                'margin_left': self.landscape_margin_left.text().strip(),
                'font_size': self.landscape_font_size.text().strip(),
                'font_family': self.landscape_font_family.text().strip(),
                'top': self.landscape_top.text().strip()
            }
            
            # Save portrait config
            portrait_config = {
                'margin_top': self.portrait_margin_top.text().strip(),
                'margin_right': self.portrait_margin_right.text().strip(),
                'margin_bottom': self.portrait_margin_bottom.text().strip(),
                'margin_left': self.portrait_margin_left.text().strip(),
                'font_size': self.portrait_font_size.text().strip(),
                'font_family': self.portrait_font_family.text().strip(),
                'top': self.portrait_top.text().strip()
            }
            
            # Validate inputs
            if not self._validate_config(landscape_config, 'landscape'):
                return
            if not self._validate_config(portrait_config, 'portrait'):
                return
            
            # Save configurations
            landscape_success = self.pdf_config_store.save_orientation_config('landscape', landscape_config)
            portrait_success = self.pdf_config_store.save_orientation_config('portrait', portrait_config)
            
            if landscape_success and portrait_success:
                self.status_label.setText("Configuración guardada exitosamente")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                QMessageBox.information(self, "Éxito", "Configuración de PDF guardada exitosamente")
                logger.info("PDF configuration saved successfully")
            else:
                self.status_label.setText("Error guardando configuración")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
                QMessageBox.warning(self, "Error", "Error guardando la configuración de PDF")
                
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            QMessageBox.critical(self, "Error", f"Error guardando configuración: {str(e)}")
            logger.error(f"Error saving PDF configs: {e}")
    
    def _validate_config(self, config: dict, orientation: str) -> bool:
        """Validate configuration parameters"""
        try:
            # Check required fields
            required_fields = ['margin_top', 'margin_right', 'margin_bottom', 'margin_left', 'font_size', 'font_family']
            for field in required_fields:
                if not config.get(field, '').strip():
                    QMessageBox.warning(self, "Error de Validación", 
                                       f"El campo '{field}' es requerido para {orientation}")
                    return False
            
            # Validate margin format (should contain 'in', 'cm', 'mm', 'px')
            margin_fields = ['margin_top', 'margin_right', 'margin_bottom', 'margin_left']
            for field in margin_fields:
                value = config[field].strip()
                if not any(unit in value for unit in ['in', 'cm', 'mm', 'px']):
                    QMessageBox.warning(self, "Error de Validación", 
                                       f"El margen '{field}' debe incluir unidad (in, cm, mm, px)")
                    return False
            
            # Validate font size format (should contain 'px', 'pt', 'em')
            font_size = config['font_size'].strip()
            if not any(unit in font_size for unit in ['px', 'pt', 'em']):
                QMessageBox.warning(self, "Error de Validación", 
                                   "El tamaño de fuente debe incluir unidad (px, pt, em)")
                return False
            
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Error de Validación", f"Error validando configuración: {str(e)}")
            return False
    
    def reset_to_defaults(self):
        """Reset configurations to default values"""
        try:
            reply = QMessageBox.question(self, "Confirmar Reset", 
                                       "¿Está seguro de que desea restaurar los valores por defecto?\n"
                                       "Esto sobrescribirá la configuración actual.",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                success = self.pdf_config_store.reset_to_defaults()
                if success:
                    self.load_current_configs()
                    self.status_label.setText("Configuración restaurada a valores por defecto")
                    self.status_label.setStyleSheet("color: green; font-weight: bold;")
                    QMessageBox.information(self, "Éxito", "Configuración restaurada a valores por defecto")
                    logger.info("PDF configuration reset to defaults")
                else:
                    self.status_label.setText("Error restaurando configuración")
                    self.status_label.setStyleSheet("color: red; font-weight: bold;")
                    QMessageBox.warning(self, "Error", "Error restaurando la configuración")
                    
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            QMessageBox.critical(self, "Error", f"Error restaurando configuración: {str(e)}")
            logger.error(f"Error resetting PDF configs: {e}")
    
    def test_config(self):
        """Test current configuration by showing a preview"""
        try:
            # Get current values
            landscape_config = {
                'margin_top': self.landscape_margin_top.text().strip(),
                'margin_right': self.landscape_margin_right.text().strip(),
                'margin_bottom': self.landscape_margin_bottom.text().strip(),
                'margin_left': self.landscape_margin_left.text().strip(),
                'font_size': self.landscape_font_size.text().strip(),
                'font_family': self.landscape_font_family.text().strip(),
                'top': self.landscape_top.text().strip()
            }
            
            portrait_config = {
                'margin_top': self.portrait_margin_top.text().strip(),
                'margin_right': self.portrait_margin_right.text().strip(),
                'margin_bottom': self.portrait_margin_bottom.text().strip(),
                'margin_left': self.portrait_margin_left.text().strip(),
                'font_size': self.portrait_font_size.text().strip(),
                'font_family': self.portrait_font_family.text().strip(),
                'top': self.portrait_top.text().strip()
            }
            
            # Show preview dialog
            preview_text = f"""Configuración Actual de PDF:

HORIZONTAL (Landscape):
- Margen Superior: {landscape_config['margin_top']}
- Margen Derecho: {landscape_config['margin_right']}
- Margen Inferior: {landscape_config['margin_bottom']}
- Margen Izquierdo: {landscape_config['margin_left']}
- Tamaño de Fuente: {landscape_config['font_size']}
- Familia de Fuente: {landscape_config['font_family']}
- Posición Vertical (top): {landscape_config['top']}

VERTICAL (Portrait):
- Margen Superior: {portrait_config['margin_top']}
- Margen Derecho: {portrait_config['margin_right']}
- Margen Inferior: {portrait_config['margin_bottom']}
- Margen Izquierdo: {portrait_config['margin_left']}
- Tamaño de Fuente: {portrait_config['font_size']}
- Familia de Fuente: {portrait_config['font_family']}
- Posición Vertical (top): {portrait_config['top']}"""
            
            QMessageBox.information(self, "Vista Previa de Configuración", preview_text)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error mostrando vista previa: {str(e)}")
            logger.error(f"Error testing PDF config: {e}")


class PrintQueueManagerGUI(QMainWindow):
    """Main window for the Print Queue Manager"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.setup_logging()
    
    def init_ui(self):
        """Initialize the main UI"""
        self.setWindowTitle("Print Queue Manager")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget with tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.printer_config_widget = PrinterConfigWidget(self)
        self.pdf_config_widget = PDFConfigWidget(self)
        self.print_queue_widget = PrintQueueWidget(self)
        self.log_widget = LogWidget(self)
        
        # Add tabs
        self.tab_widget.addTab(self.printer_config_widget, "Printer Configuration")
        self.tab_widget.addTab(self.pdf_config_widget, "Configuración PDF")
        self.tab_widget.addTab(self.print_queue_widget, "Print Queue")
        self.tab_widget.addTab(self.log_widget, "Logs")
        
        layout.addWidget(self.tab_widget)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Print Queue Manager Ready")
        
        # Timer for status updates
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)  # Update every 5 seconds
    
    def setup_logging(self):
        """Setup logging to display in the log widget"""
        class GUILogHandler(logging.Handler):
            def __init__(self, log_widget):
                super().__init__()
                self.log_widget = log_widget
            
            def emit(self, record):
                try:
                    msg = self.format(record)
                    self.log_widget.append_log(msg)
                except:
                    pass
        
        # Add GUI log handler
        gui_handler = GUILogHandler(self.log_widget)
        gui_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(gui_handler)
        root_logger.setLevel(logging.INFO)
        
        logger.info("Print Queue Manager GUI started")
    
    def update_status(self):
        """Update status bar"""
        try:
            # Get number of configured printers
            all_configs = printer_config_store.get_all_configurations()
            configured_printers = len([p for p in all_configs.values() 
                                     if any(cfg.get('is_configured', False) 
                                           for cfg in p.values())])
            
            # Get total printers
            total_printers = len([printer[2] for printer in win32print.EnumPrinters(2)])
            
            self.status_bar.showMessage(
                f"Printers: {configured_printers}/{total_printers} configured | "
                f"Service: Running")
            
        except Exception as e:
            self.status_bar.showMessage(f"Status update error: {str(e)}")
    
    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("Print Queue Manager GUI closing")
        event.accept()


def run_gui():
    """Run the PyQt GUI application"""
    app = QApplication(sys.argv)
    app.setApplicationName("Print Queue Manager")
    app.setApplicationVersion("1.0")
    
    # Create and show main window
    main_window = PrintQueueManagerGUI()
    main_window.show()
    
    return app.exec()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    run_gui()