"""
Configuration Store for Printer Settings
Handles persistence of DEVMODE and DEVNAMES data per printer and orientation
"""
import json
import os
import pickle
import base64
from typing import Dict, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class PDFConfigStore:
    """
    Stores PDF configuration parameters.
    Handles settings like page size, margins, orientation, etc.
    """
    
    def __init__(self, config_dir: str = "pdf_configs"):
        """
        Initialize PDF configuration store.
        
        Args:
            config_dir: Directory to store PDF configuration files
        """
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, "pdf_configs.json")
        
        # Create directory if it doesn't exist
        os.makedirs(config_dir, exist_ok=True)
        
        # Load existing configurations
        self.configs = self._load_configs()
    
    def _load_configs(self) -> Dict[str, Any]:
        """Load PDF configurations from disk."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading PDF configs: {e}")
                return {}
        return {}
    
    def _save_configs(self):
        """Save PDF configurations to disk."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.configs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving PDF configs: {e}")
    
    def save_pdf_config(self, config_name: str, **kwargs) -> bool:
        """
        Save PDF configuration.
        
        Args:
            config_name: Name of the configuration
            **kwargs: PDF parameters (page_size, margins, orientation, etc.)
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            self.configs[config_name] = {
                'config_name': config_name,
                'page_size': kwargs.get('page_size', 'A4'),
                'orientation': kwargs.get('orientation', 'portrait'),
                'margin_top': kwargs.get('margin_top', 20),
                'margin_bottom': kwargs.get('margin_bottom', 20),
                'margin_left': kwargs.get('margin_left', 20),
                'margin_right': kwargs.get('margin_right', 20),
                'font_size': kwargs.get('font_size', 12),
                'font_family': kwargs.get('font_family', 'Arial'),
                'quality': kwargs.get('quality', 'high'),
                'compression': kwargs.get('compression', True),
                'last_modified': str(os.path.getmtime(self.config_file)) if os.path.exists(self.config_file) else ""
            }
            
            self._save_configs()
            logger.info(f"Saved PDF config: {config_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving PDF config: {e}")
            return False
    
    def load_pdf_config(self, config_name: str) -> Optional[Dict[str, Any]]:
        """
        Load PDF configuration.
        
        Args:
            config_name: Name of the configuration
            
        Returns:
            Configuration dictionary or None if not found
        """
        try:
            if config_name in self.configs:
                logger.info(f"Loaded PDF config: {config_name}")
                return self.configs[config_name]
            else:
                logger.warning(f"PDF config not found: {config_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading PDF config: {e}")
            return None
    
    def get_all_pdf_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all PDF configurations.
        
        Returns:
            Dictionary with all PDF configurations
        """
        return self.configs.copy()
    
    def delete_pdf_config(self, config_name: str) -> bool:
        """
        Delete PDF configuration.
        
        Args:
            config_name: Name of the configuration to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if config_name in self.configs:
                del self.configs[config_name]
                self._save_configs()
                logger.info(f"Deleted PDF config: {config_name}")
                return True
            else:
                logger.warning(f"PDF config not found for deletion: {config_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting PDF config: {e}")
            return False

class PDFOrientationConfigStore:
    """
    Stores PDF orientation-specific parameters (margins, fonts, etc.)
    Handles landscape and portrait configurations separately.
    """
    
    def __init__(self, config_dir: str = "pdf_configs"):
        """
        Initialize PDF orientation configuration store.
        
        Args:
            config_dir: Directory to store PDF configuration files
        """
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, "pdf_orientation_configs.json")
        
        # Create directory if it doesn't exist
        os.makedirs(config_dir, exist_ok=True)
        
        # Default configurations
        self.default_configs = {
            'landscape': {
                'margin_top': '0in',
                'margin_right': '0.78in',
                'margin_bottom': '0in',
                'margin_left': '0.4in',
                'font_size': '13px',
                'font_family': "'Courier New', Courier, monospace",
                'top': '0px'
            },
            'portrait': {
                'margin_top': '0in',
                'margin_right': '0.3in',
                'margin_bottom': '0in',
                'margin_left': '0.3in',
                'font_size': '17px',
                'font_family': "'Calibri', sans-serif",
                'top': '0px'
            }
        }
        
        # Load existing configurations
        self.configs = self._load_configs()
    
    def _load_configs(self) -> Dict[str, Dict[str, str]]:
        """Load PDF orientation configurations from disk."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_configs = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    for orientation in self.default_configs:
                        if orientation not in loaded_configs:
                            loaded_configs[orientation] = self.default_configs[orientation].copy()
                        else:
                            # Ensure all default keys exist
                            for key, value in self.default_configs[orientation].items():
                                if key not in loaded_configs[orientation]:
                                    loaded_configs[orientation][key] = value
                    return loaded_configs
            except Exception as e:
                logger.error(f"Error loading PDF orientation configs: {e}")
                return self.default_configs.copy()
        return self.default_configs.copy()
    
    def _save_configs(self):
        """Save PDF orientation configurations to disk."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.configs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving PDF orientation configs: {e}")
    
    def get_orientation_config(self, orientation: str) -> Dict[str, str]:
        """
        Get configuration for specific orientation.
        
        Args:
            orientation: 'landscape' or 'portrait'
            
        Returns:
            Configuration dictionary for the orientation
        """
        orientation = orientation.lower()
        if orientation in self.configs:
            return self.configs[orientation].copy()
        else:
            logger.warning(f"Orientation config not found: {orientation}, using default")
            return self.default_configs.get(orientation, {}).copy()
    
    def save_orientation_config(self, orientation: str, config: Dict[str, str]) -> bool:
        """
        Save configuration for specific orientation.
        
        Args:
            orientation: 'landscape' or 'portrait'
            config: Configuration dictionary
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            orientation = orientation.lower()
            if orientation not in ['landscape', 'portrait']:
                logger.error(f"Invalid orientation: {orientation}")
                return False
            
            self.configs[orientation] = config.copy()
            self._save_configs()
            logger.info(f"Saved PDF orientation config: {orientation}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving PDF orientation config: {e}")
            return False
    
    def reset_to_defaults(self, orientation: str = None) -> bool:
        """
        Reset configuration to defaults.
        
        Args:
            orientation: Specific orientation to reset, or None for all
            
        Returns:
            True if reset successfully, False otherwise
        """
        try:
            if orientation:
                orientation = orientation.lower()
                if orientation in self.default_configs:
                    self.configs[orientation] = self.default_configs[orientation].copy()
                    logger.info(f"Reset PDF orientation config to default: {orientation}")
                else:
                    logger.error(f"Invalid orientation: {orientation}")
                    return False
            else:
                self.configs = self.default_configs.copy()
                logger.info("Reset all PDF orientation configs to defaults")
            
            self._save_configs()
            return True
            
        except Exception as e:
            logger.error(f"Error resetting PDF orientation config: {e}")
            return False
 
class PrinterConfigStore:
    """
    Stores printer configurations (DEVMODE + DEVNAMES) per printer and orientation.
    Format: {printer_name}:{orientation} -> serialized_config
    """
    
    def __init__(self, config_dir: str = "printer_configs"):
        """
        Initialize configuration store.
        
        Args:
            config_dir: Directory to store configuration files
        """
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, "printer_configs.json")
        self.binary_data_dir = os.path.join(config_dir, "binary_data")
        
        # Create directories if they don't exist
        os.makedirs(config_dir, exist_ok=True)
        os.makedirs(self.binary_data_dir, exist_ok=True)
        
        # Load existing configurations
        self.configs = self._load_configs()
    
    def _load_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load configurations from disk."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading configs: {e}")
                return {}
        return {}
    
    def _save_configs(self):
        """Save configurations to disk."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.configs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving configs: {e}")
    
    def _get_key(self, printer_name: str, orientation: str) -> str:
        """Generate configuration key."""
        return f"{printer_name}:{orientation.lower()}"
    
    def _get_binary_file_path(self, key: str, data_type: str) -> str:
        """Get path for binary data file."""
        safe_key = key.replace(':', '_').replace('\\', '_').replace('/', '_')
        return os.path.join(self.binary_data_dir, f"{safe_key}_{data_type}.bin")
    
    def save_printer_config(self, printer_name: str, orientation: str, 
                          devmode_data: bytes, devnames_data: bytes,
                          paper_size: str = "", duplex: str = "", 
                          color: str = "", tray: str = "") -> bool:
        """
        Save printer configuration.
        
        Args:
            printer_name: Name of the printer
            orientation: "portrait" or "landscape"
            devmode_data: Serialized DEVMODE structure
            devnames_data: Serialized DEVNAMES structure
            paper_size: Human readable paper size
            duplex: Human readable duplex setting
            color: Human readable color setting
            tray: Human readable tray setting
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            key = self._get_key(printer_name, orientation)
            
            # Save binary data to separate files
            devmode_file = self._get_binary_file_path(key, "devmode")
            devnames_file = self._get_binary_file_path(key, "devnames")
            
            with open(devmode_file, 'wb') as f:
                f.write(devmode_data)
            
            with open(devnames_file, 'wb') as f:
                f.write(devnames_data)
            
            # Save metadata in JSON
            self.configs[key] = {
                'printer_name': printer_name,
                'orientation': orientation.lower(),
                'devmode_file': devmode_file,
                'devnames_file': devnames_file,
                'paper_size': paper_size,
                'duplex': duplex,
                'color': color,
                'tray': tray,
                'configured': True,
                'last_modified': str(os.path.getmtime(devmode_file)) if os.path.exists(devmode_file) else ""
            }
            
            self._save_configs()
            logger.info(f"Saved config for {printer_name}:{orientation}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving printer config: {e}")
            return False
    
    def load_printer_config(self, printer_name: str, orientation: str) -> Optional[Tuple[bytes, bytes, Dict[str, str]]]:
        """
        Load printer configuration.
        
        Args:
            printer_name: Name of the printer
            orientation: "portrait" or "landscape"
            
        Returns:
            Tuple of (devmode_data, devnames_data, metadata) or None if not found
        """
        try:
            key = self._get_key(printer_name, orientation)
            
            if key not in self.configs:
                logger.warning(f"No config found for {printer_name}:{orientation}")
                return None
            
            config = self.configs[key]
            
            # Load binary data
            devmode_file = config.get('devmode_file')
            devnames_file = config.get('devnames_file')
            
            if not devmode_file or not devnames_file:
                logger.error(f"Missing file paths in config for {key}")
                return None
            
            if not os.path.exists(devmode_file) or not os.path.exists(devnames_file):
                logger.error(f"Binary files missing for {key}")
                return None
            
            with open(devmode_file, 'rb') as f:
                devmode_data = f.read()
            
            with open(devnames_file, 'rb') as f:
                devnames_data = f.read()
            
            metadata = {
                'paper_size': config.get('paper_size', ''),
                'duplex': config.get('duplex', ''),
                'color': config.get('color', ''),
                'tray': config.get('tray', ''),
                'last_modified': config.get('last_modified', '')
            }
            
            logger.info(f"Loaded config for {printer_name}:{orientation}")
            return (devmode_data, devnames_data, metadata)
            
        except Exception as e:
            logger.error(f"Error loading printer config: {e}")
            return None
    
    def is_configured(self, printer_name: str, orientation: str) -> bool:
        """
        Check if printer and orientation combination is configured.
        
        Args:
            printer_name: Name of the printer
            orientation: "portrait" or "landscape"
            
        Returns:
            True if configured, False otherwise
        """
        key = self._get_key(printer_name, orientation)
        config = self.configs.get(key, {})
        return config.get('configured', False) and \
               os.path.exists(config.get('devmode_file', '')) and \
               os.path.exists(config.get('devnames_file', ''))
    
    def get_printer_configurations(self, printer_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all configurations for a specific printer.
        
        Args:
            printer_name: Name of the printer
            
        Returns:
            Dictionary with orientation as key and config data as value
        """
        result = {}
        for orientation in ['portrait', 'landscape']:
            key = self._get_key(printer_name, orientation)
            if key in self.configs:
                config = self.configs[key].copy()
                config['is_configured'] = self.is_configured(printer_name, orientation)
                result[orientation] = config
            else:
                result[orientation] = {
                    'is_configured': False,
                    'orientation': orientation,
                    'printer_name': printer_name
                }
        return result
    
    def get_all_configurations(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all printer configurations.
        
        Returns:
            Dictionary with printer names as keys and configurations as values
        """
        result = {}
        for key, config in self.configs.items():
            printer_name = config.get('printer_name', '')
            if printer_name not in result:
                result[printer_name] = {}
            
            orientation = config.get('orientation', '')
            config_copy = config.copy()
            config_copy['is_configured'] = self.is_configured(printer_name, orientation)
            result[printer_name][orientation] = config_copy
        
        return result
    
    def delete_printer_config(self, printer_name: str, orientation: str = None) -> bool:
        """
        Delete printer configuration.
        
        Args:
            printer_name: Name of the printer
            orientation: Specific orientation to delete, or None to delete all
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if orientation:
                # Delete specific orientation
                key = self._get_key(printer_name, orientation)
                if key in self.configs:
                    config = self.configs[key]
                    
                    # Delete binary files
                    for file_path in [config.get('devmode_file'), config.get('devnames_file')]:
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                    
                    # Remove from configs
                    del self.configs[key]
            else:
                # Delete all orientations for this printer
                keys_to_delete = [k for k in self.configs.keys() if k.startswith(f"{printer_name}:")]
                for key in keys_to_delete:
                    config = self.configs[key]
                    
                    # Delete binary files
                    for file_path in [config.get('devmode_file'), config.get('devnames_file')]:
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                    
                    # Remove from configs
                    del self.configs[key]
            
            self._save_configs()
            logger.info(f"Deleted config for {printer_name}:{orientation or 'all'}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting printer config: {e}")
            return False

# Global instance
printer_config_store = PrinterConfigStore()