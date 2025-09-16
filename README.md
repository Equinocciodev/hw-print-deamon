# Print Queue Manager Daemon

A Windows-only print daemon service for integration with **Odoo 16** that provides native printer configuration using Windows PrintDlgEx dialogs and logical print queues.

## Features

- **Native Windows PrintDlgEx Integration**: Configure printers using native Windows dialogs with full driver support
- **Per-Printer Per-Orientation Configuration**: Separate settings for Portrait and Landscape orientations
- **Logical Print Queues**: Individual queues for each printer with job management
- **PyQt6 GUI Interface**: User-friendly interface for printer configuration and queue monitoring
- **Full Odoo Compatibility**: Maintains exact API compatibility with existing `call_to_api.js`
- **DEVMODE/DEVNAMES Persistence**: Stores native Windows printer configurations
- **Error Handling**: Comprehensive error reporting and graceful fallbacks

## Requirements

- Windows OS (Windows 10/11 recommended)
- Python 3.9+
- Administrator privileges (for printer configuration)
- Installed printers with proper drivers
- **Ghostscript** (for native PDF printing without Adobe)

## Installation

1. **Install Ghostscript** (required for native printing):
   - Download from: https://www.ghostscript.com/download/gsdnld.html
   - Install the Windows version (GPL or AGPL)
   - Ensure `gswin64c.exe` or `gswin32c.exe` is in your system PATH
   - Alternative: Extract to project's `bin/` directory as `ghostscript.exe`

2. **Install Python Dependencies**:
   ```powershell
   "C:\Users\Lightning\AppData\Local\Programs\Python\Python313\python.exe" -m pip install -r requirements_win.txt
   ```

3. **Verify Installation**:
   ```powershell
   "C:\Users\Lightning\AppData\Local\Programs\Python\Python313\python.exe" daemon_main.py --help
   ```

## Usage

### Start with GUI (Recommended)

```powershell
"C:\Users\Lightning\AppData\Local\Programs\Python\Python313\python.exe" daemon_main.py
```

This starts both:
- REST API server on `http://localhost:8000`
- PyQt GUI interface for configuration

### Start API Only (Headless)

```powershell
"C:\Users\Lightning\AppData\Local\Programs\Python\Python313\python.exe" daemon_main.py --api-only
```

This starts only the REST API server without GUI.

## Configuration Workflow

### 1. Initial Setup

1. **Start the daemon** with GUI mode
2. **Navigate to "Printer Configuration" tab**
3. **Click "Refresh Printers"** to discover available printers

### 2. Configure Each Printer

For each printer you want to use with Odoo:

1. **Click "Configure Portrait"** button for the printer
2. **Windows native print dialog opens**
3. **Configure**: paper size, orientation, color, duplex, trays, etc.
4. **Click "OK"** to save configuration
5. **Repeat for "Configure Landscape"** if needed

### 3. Verify Configuration

- ✓ Green checkmarks indicate configured orientations
- Configuration details show paper size, color settings
- "Status" column shows overall configuration state

### 4. Monitor Print Jobs

- **"Print Queue" tab** shows active and completed jobs
- **Real-time status** of print operations
- **Error reporting** for failed jobs

## API Endpoints

The daemon provides the same REST API that Odoo expects:

### GET /printers
Lists available printers.

**Response**:
```json
{
  "printers": ["Printer1", "Printer2", "..."]
}
```

### POST /dotmatrix/print
Submits a print job.

**Request** (form data):
- `printer_data`: HTML content to print
- `orientation`: "portrait" or "landscape"  
- `printer`: Target printer name

**Response**:
```json
{
  "status": "OK"
}
```

### Additional Endpoints (Optional)

- `GET /printer-status` - Get printer configuration status
- `GET /queue-status` - Get print queue status

## Integration with Odoo

**No changes needed to Odoo or `call_to_api.js`!**

The daemon maintains full compatibility:
1. **Same endpoints**: `/printers` and `/dotmatrix/print`
2. **Same request/response format**
3. **Same HTTP methods and status codes**

Your existing `call_to_api.js` will work without modifications.

## File Structure

```
hw-print-deamon/
├── daemon_main.py              # Main launcher
├── main.py                     # Flask API server
├── lib/
│   ├── config_store.py         # Configuration persistence
│   ├── win32_printdlgex.py     # Win32 PrintDlgEx wrapper
│   ├── print_manager.py        # Print queue management
│   ├── qt_ui.py               # PyQt GUI interface
│   ├── windows.py             # Enhanced Windows printing
│   └── pdf.py                 # PDF generation
├── printer_configs/           # Stored configurations
├── pdf/                       # Generated PDF files
└── requirements_win.txt       # Python dependencies
```

## Configuration Storage

Printer configurations are stored in:
- **`printer_configs/printer_configs.json`** - Metadata and settings
- **`printer_configs/binary_data/`** - Binary DEVMODE/DEVNAMES data

Each printer stores two configurations:
- `{PrinterName}:portrait` - Portrait orientation settings
- `{PrinterName}:landscape` - Landscape orientation settings

## Troubleshooting

### Common Issues

1. **"Printer not configured" error**
   - Use GUI to configure the printer for required orientation
   - Ensure both Portrait and Landscape are configured if needed

2. **PrintDlgEx dialog doesn't open**
   - Run as Administrator
   - Verify printer drivers are properly installed
   - Check Windows printer settings

3. **Print jobs fail**
   - Check printer is online and has paper
   - Verify printer permissions
   - Check Windows Event Viewer for driver errors

4. **GUI doesn't start**
   - Verify PyQt6 installation
   - Check display settings and DPI scaling
   - Run from command line to see error messages

### Logging

Logs are written to:
- **Console output** (when running interactively)
- **`print_daemon.log`** file (when running as daemon)

Increase log level by modifying logging configuration in `daemon_main.py`.

### Testing API Compatibility

Run the compatibility test:
```powershell
# Start daemon in one terminal
"C:\Users\Lightning\AppData\Local\Programs\Python\Python313\python.exe" daemon_main.py --api-only

# Test in another terminal
"C:\Users\Lightning\AppData\Local\Programs\Python\Python313\python.exe" test_api_compatibility.py
```

## Architecture

### Key Components

1. **Win32 PrintDlgEx Wrapper** (`win32_printdlgex.py`)
   - Native Windows API integration
   - DEVMODE/DEVNAMES handling
   - Memory management for Win32 structures

2. **Configuration Store** (`config_store.py`)
   - Persistent storage of printer settings
   - JSON metadata + binary data files
   - Per-printer per-orientation organization

3. **Print Queue Manager** (`print_manager.py`)
   - Logical queues for each printer
   - Threaded job processing
   - Status tracking and error handling

4. **PyQt GUI** (`qt_ui.py`)
   - Printer configuration interface
   - Queue monitoring and status display
   - Native Windows dialog integration

5. **Flask API Server** (`main.py`)
   - REST endpoints for Odoo integration
   - Request validation and error handling
   - Compatibility with existing JavaScript client

### Design Principles

- **API Compatibility**: Never break existing Odoo integration
- **Native Configuration**: Use Windows native dialogs and drivers
- **Graceful Fallbacks**: Handle errors without breaking print flow
- **Threaded Processing**: Non-blocking print job handling
- **Comprehensive Logging**: Detailed logging for troubleshooting

## Development

### Adding New Features

1. **Extend API**: Add new endpoints in `main.py` (don't modify existing ones)
2. **GUI Enhancements**: Modify `qt_ui.py` for new interface features
3. **Print Processing**: Extend `print_manager.py` for new queue behaviors
4. **Configuration**: Extend `config_store.py` for new settings

### Testing

1. **Unit Tests**: Test individual components
2. **Integration Tests**: Test API compatibility
3. **UI Tests**: Test GUI functionality
4. **End-to-End Tests**: Test with actual Odoo integration

## Support

For issues and questions:
1. Check the logs for error details
2. Verify printer driver installation
3. Test with Windows built-in print test page
4. Ensure administrator privileges for configuration

## License

This project is designed specifically for integration with Odoo 16 print workflows.