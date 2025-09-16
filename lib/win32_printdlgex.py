"""
Win32 PrintDlgEx API Wrapper
Handles native Windows printer configuration dialogs using PrintDlgEx
"""
import ctypes
from ctypes import wintypes, Structure, POINTER, byref, c_char_p, c_void_p
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# Win32 API Constants
PD_ALLPAGES = 0x00000000
PD_SELECTION = 0x00000001
PD_PAGENUMS = 0x00000002
PD_NOSELECTION = 0x00000004
PD_NOPAGENUMS = 0x00000008
PD_COLLATE = 0x00000010
PD_PRINTTOFILE = 0x00000020
PD_PRINTSETUP = 0x00000040
PD_NOWARNING = 0x00000080
PD_RETURNDC = 0x00000100
PD_RETURNIC = 0x00000200
PD_RETURNDEFAULT = 0x00000400
PD_SHOWHELP = 0x00000800
PD_ENABLEPRINTHOOK = 0x00001000
PD_ENABLESETUPHOOK = 0x00002000
PD_ENABLEPRINTTEMPLATE = 0x00004000
PD_ENABLESETUPTEMPLATE = 0x00008000
PD_ENABLEPRINTTEMPLATEHANDLE = 0x00010000
PD_ENABLESETUPTEMPLATEHANDLE = 0x00020000
PD_USEDEVMODECOPIES = 0x00040000
PD_USEDEVMODECOPIESANDCOLLATE = 0x00040000
PD_DISABLEPRINTTOFILE = 0x00080000
PD_HIDEPRINTTOFILE = 0x00100000
PD_NONETWORKBUTTON = 0x00200000
PD_CURRENTPAGE = 0x00400000
PD_NOCURRENTPAGE = 0x00800000
PD_EXCLUSIONFLAGS = 0x01000000
PD_USELARGETEMPLATE = 0x10000000

# PrintDlgEx result actions
PD_RESULT_CANCEL = 0
PD_RESULT_PRINT = 1
PD_RESULT_APPLY = 2

# DEVMODE constants
DM_ORIENTATION = 0x00000001
DM_PAPERSIZE = 0x00000002
DM_PAPERLENGTH = 0x00000004
DM_PAPERWIDTH = 0x00000008
DM_SCALE = 0x00000010
DM_COPIES = 0x00000100
DM_DEFAULTSOURCE = 0x00000200
DM_PRINTQUALITY = 0x00000400
DM_COLOR = 0x00000800
DM_DUPLEX = 0x00001000
DM_YRESOLUTION = 0x00002000
DM_TTOPTION = 0x00004000
DM_COLLATE = 0x00008000

# Orientation constants
DMORIENT_PORTRAIT = 1
DMORIENT_LANDSCAPE = 2

# Duplex constants
DMDUP_SIMPLEX = 1
DMDUP_VERTICAL = 2
DMDUP_HORIZONTAL = 3

# Color constants
DMCOLOR_MONOCHROME = 1
DMCOLOR_COLOR = 2


class PRINTPAGERANGE(Structure):
    """Win32 PRINTPAGERANGE structure"""
    _fields_ = [
        ("nFromPage", wintypes.DWORD),
        ("nToPage", wintypes.DWORD),
    ]


class DEVMODE(Structure):
    """Win32 DEVMODE structure (simplified version)"""
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmOrientation", wintypes.SHORT),
        ("dmPaperSize", wintypes.SHORT),
        ("dmPaperLength", wintypes.SHORT),
        ("dmPaperWidth", wintypes.SHORT),
        ("dmScale", wintypes.SHORT),
        ("dmCopies", wintypes.SHORT),
        ("dmDefaultSource", wintypes.SHORT),
        ("dmPrintQuality", wintypes.SHORT),
        ("dmColor", wintypes.SHORT),
        ("dmDuplex", wintypes.SHORT),
        ("dmYResolution", wintypes.SHORT),
        ("dmTTOption", wintypes.SHORT),
        ("dmCollate", wintypes.SHORT),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
    ]


class DEVNAMES(Structure):
    """Win32 DEVNAMES structure"""
    _fields_ = [
        ("wDriverOffset", wintypes.WORD),
        ("wDeviceOffset", wintypes.WORD),
        ("wOutputOffset", wintypes.WORD),
        ("wDefault", wintypes.WORD),
    ]


class PRINTDLGEX(Structure):
    """Win32 PRINTDLGEX structure"""
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hDevMode", wintypes.HGLOBAL),
        ("hDevNames", wintypes.HGLOBAL),
        ("hDC", wintypes.HDC),
        ("Flags", wintypes.DWORD),
        ("Flags2", wintypes.DWORD),
        ("ExclusionFlags", wintypes.DWORD),
        ("nPageRanges", wintypes.DWORD),
        ("nMaxPageRanges", wintypes.DWORD),
        ("lpPageRanges", POINTER(PRINTPAGERANGE)),
        ("nMinPage", wintypes.DWORD),
        ("nMaxPage", wintypes.DWORD),
        ("nCopies", wintypes.DWORD),
        ("hInstance", wintypes.HINSTANCE),
        ("lpPrintTemplateName", wintypes.LPCWSTR),
        ("lpCallback", c_void_p),
        ("nPropertyPages", wintypes.DWORD),
        ("lphPropertyPages", c_void_p),  # Using c_void_p instead of HPROPSHEETPAGE
        ("nStartPage", wintypes.DWORD),
        ("dwResultAction", wintypes.DWORD),
    ]


class Win32PrintDlgWrapper:
    """Wrapper for Win32 PrintDlgEx API"""
    
    def __init__(self):
        """Initialize Win32 API functions"""
        try:
            # Load required DLLs
            self.comdlg32 = ctypes.windll.comdlg32
            self.kernel32 = ctypes.windll.kernel32
            self.winspool = ctypes.windll.LoadLibrary("winspool.drv")  # Use LoadLibrary for winspool.drv
            
            # Define function prototypes
            self.comdlg32.PrintDlgExW.argtypes = [POINTER(PRINTDLGEX)]
            self.comdlg32.PrintDlgExW.restype = wintypes.LONG  # HRESULT is equivalent to LONG
            
            self.kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
            self.kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
            
            self.kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            self.kernel32.GlobalLock.restype = c_void_p
            
            self.kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            self.kernel32.GlobalUnlock.restype = wintypes.BOOL
            
            self.kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
            self.kernel32.GlobalFree.restype = wintypes.HGLOBAL
            
            self.kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
            self.kernel32.GlobalSize.restype = ctypes.c_size_t
            
            # DocumentProperties function for proper DEVMODE handling
            self.winspool.DocumentPropertiesW.argtypes = [
                wintypes.HWND,      # hwnd
                wintypes.HANDLE,    # hPrinter
                wintypes.LPCWSTR,   # pDeviceName
                POINTER(DEVMODE),   # pDevModeOutput
                POINTER(DEVMODE),   # pDevModeInput
                wintypes.DWORD      # fMode
            ]
            self.winspool.DocumentPropertiesW.restype = wintypes.LONG
            
            # OpenPrinter and ClosePrinter
            self.winspool.OpenPrinterW.argtypes = [wintypes.LPCWSTR, POINTER(wintypes.HANDLE), c_void_p]
            self.winspool.OpenPrinterW.restype = wintypes.BOOL
            
            self.winspool.ClosePrinter.argtypes = [wintypes.HANDLE]
            self.winspool.ClosePrinter.restype = wintypes.BOOL
            
            logger.info("Win32 PrintDlgEx wrapper initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Win32 PrintDlgEx wrapper: {e}")
            raise
    
    def _create_devmode_global(self, devmode_data: bytes = None) -> wintypes.HGLOBAL:
        """Create a global memory block for DEVMODE"""
        try:
            if devmode_data:
                size = len(devmode_data)
            else:
                size = ctypes.sizeof(DEVMODE) + 1024  # Extra space for driver private data
            
            hglobal = self.kernel32.GlobalAlloc(0x0042, size)  # GMEM_MOVEABLE | GMEM_ZEROINIT
            if not hglobal:
                raise Exception("Failed to allocate global memory for DEVMODE")
            
            if devmode_data:
                # Copy existing data
                ptr = self.kernel32.GlobalLock(hglobal)
                if ptr:
                    ctypes.memmove(ptr, devmode_data, len(devmode_data))
                    self.kernel32.GlobalUnlock(hglobal)
            
            return hglobal
            
        except Exception as e:
            logger.error(f"Error creating DEVMODE global: {e}")
            return None
    
    def _create_devnames_global(self, printer_name: str = None) -> wintypes.HGLOBAL:
        """Create a global memory block for DEVNAMES"""
        try:
            if not printer_name:
                return None
                
            # Calculate required size
            driver_name = "winspool"  # Standard Windows driver
            port_name = ""  # Will be filled by system
            
            # Size calculation: structure + strings + null terminators
            size = ctypes.sizeof(DEVNAMES) + \
                   (len(driver_name) + 1) * 2 + \
                   (len(printer_name) + 1) * 2 + \
                   (len(port_name) + 1) * 2
            
            hglobal = self.kernel32.GlobalAlloc(0x0042, size)  # GMEM_MOVEABLE | GMEM_ZEROINIT
            if not hglobal:
                raise Exception("Failed to allocate global memory for DEVNAMES")
            
            ptr = self.kernel32.GlobalLock(hglobal)
            if ptr:
                devnames = DEVNAMES.from_address(ptr)
                
                # Set up offsets
                offset = ctypes.sizeof(DEVNAMES) // 2  # Offset in WCHARs
                devnames.wDriverOffset = offset
                
                # Copy driver name
                driver_bytes = (driver_name + '\0').encode('utf-16le')
                ctypes.memmove(ptr + offset * 2, driver_bytes, len(driver_bytes))
                offset += len(driver_name) + 1
                
                devnames.wDeviceOffset = offset
                # Copy device name
                device_bytes = (printer_name + '\0').encode('utf-16le')
                ctypes.memmove(ptr + offset * 2, device_bytes, len(device_bytes))
                offset += len(printer_name) + 1
                
                devnames.wOutputOffset = offset
                # Copy output name (empty)
                output_bytes = (port_name + '\0').encode('utf-16le')
                ctypes.memmove(ptr + offset * 2, output_bytes, len(output_bytes))
                
                devnames.wDefault = 0  # Not default
                
                self.kernel32.GlobalUnlock(hglobal)
            
            return hglobal
            
        except Exception as e:
            logger.error(f"Error creating DEVNAMES global: {e}")
            return None
    
    def _extract_global_data(self, hglobal: wintypes.HGLOBAL) -> Optional[bytes]:
        """Extract data from global memory handle"""
        try:
            if not hglobal:
                return None
                
            size = self.kernel32.GlobalSize(hglobal)
            if size == 0:
                return None
                
            ptr = self.kernel32.GlobalLock(hglobal)
            if not ptr:
                return None
                
            # Copy data
            data = (ctypes.c_byte * size).from_address(ptr)
            result = bytes(data)
            
            self.kernel32.GlobalUnlock(hglobal)
            return result
            
        except Exception as e:
            logger.error(f"Error extracting global data: {e}")
            return None
    
    def show_print_properties_dialog(self, hwnd_owner: int, printer_name: str,
                                   existing_devmode: bytes = None,
                                   existing_devnames: bytes = None) -> Optional[Tuple[bytes, bytes, Dict[str, Any]]]:
        """
        Show native Windows print properties dialog using PrintDlgEx.
        
        Args:
            hwnd_owner: Handle to owner window
            printer_name: Name of the printer to configure
            existing_devmode: Existing DEVMODE data (optional)
            existing_devnames: Existing DEVNAMES data (optional)
            
        Returns:
            Tuple of (devmode_data, devnames_data, metadata) or None if cancelled
        """
        try:
            # Initialize PRINTDLGEX structure
            pdlg = PRINTDLGEX()
            pdlg.lStructSize = ctypes.sizeof(PRINTDLGEX)
            pdlg.hwndOwner = hwnd_owner
            
            # Set flags
            pdlg.Flags = (PD_RETURNDC | 
                         PD_USEDEVMODECOPIESANDCOLLATE | 
                         PD_NOPAGENUMS | 
                         PD_NOSELECTION)
            
            # Create or use existing DEVMODE
            if existing_devmode:
                pdlg.hDevMode = self._create_devmode_global(existing_devmode)
            else:
                pdlg.hDevMode = self._create_devmode_global()
            
            # Create or use existing DEVNAMES
            if existing_devnames:
                # Use existing DEVNAMES (should contain printer name)
                pdlg.hDevNames = self.kernel32.GlobalAlloc(0x0042, len(existing_devnames))
                if pdlg.hDevNames:
                    ptr = self.kernel32.GlobalLock(pdlg.hDevNames)
                    if ptr:
                        ctypes.memmove(ptr, existing_devnames, len(existing_devnames))
                        self.kernel32.GlobalUnlock(pdlg.hDevNames)
            else:
                pdlg.hDevNames = self._create_devnames_global(printer_name)
            
            # Initialize other fields
            pdlg.nCopies = 1
            pdlg.nMinPage = 1
            pdlg.nMaxPage = 1
            pdlg.nPageRanges = 0
            pdlg.nMaxPageRanges = 0
            
            logger.info(f"Showing print properties dialog for {printer_name}")
            
            # Show the dialog
            result = self.comdlg32.PrintDlgExW(byref(pdlg))
            
            if result != 0:  # S_OK
                logger.warning(f"PrintDlgExW failed with HRESULT: 0x{result:08x}, will try alternative method")
                return None
            
            # Check what the user did
            if pdlg.dwResultAction == PD_RESULT_CANCEL:
                logger.info("User cancelled print properties dialog")
                return None
            
            if pdlg.dwResultAction in [PD_RESULT_PRINT, PD_RESULT_APPLY]:
                logger.info(f"User action: {pdlg.dwResultAction}")
                
                # Extract DEVMODE and DEVNAMES data
                devmode_data = self._extract_global_data(pdlg.hDevMode)
                devnames_data = self._extract_global_data(pdlg.hDevNames)
                
                if not devmode_data:
                    logger.error("Failed to extract DEVMODE data")
                    return None
                
                # Extract metadata from DEVMODE
                metadata = self._extract_devmode_metadata(devmode_data)
                
                logger.info("Successfully captured printer configuration")
                return (devmode_data, devnames_data, metadata)
            
            return None
            
        except Exception as e:
            logger.error(f"Error showing print properties dialog: {e}")
            return None
            
        finally:
            # Clean up global memory
            try:
                if 'pdlg' in locals():
                    if pdlg.hDevMode:
                        self.kernel32.GlobalFree(pdlg.hDevMode)
                    if pdlg.hDevNames:
                        self.kernel32.GlobalFree(pdlg.hDevNames)
                    if pdlg.hDC:
                        ctypes.windll.gdi32.DeleteDC(pdlg.hDC)
            except Exception as e:
                logger.error(f"Error cleaning up: {e}")
    
    def _extract_devmode_metadata(self, devmode_data: bytes) -> Dict[str, Any]:
        """Extract human-readable metadata from DEVMODE data"""
        try:
            if len(devmode_data) < ctypes.sizeof(DEVMODE):
                return {}
            
            # Create DEVMODE structure from data
            devmode = DEVMODE.from_buffer_copy(devmode_data[:ctypes.sizeof(DEVMODE)])
            
            metadata = {
                'device_name': devmode.dmDeviceName.rstrip('\x00'),
                'paper_size': self._get_paper_size_name(devmode.dmPaperSize) if devmode.dmFields & DM_PAPERSIZE else "Default",
                'orientation': "Portrait" if devmode.dmOrientation == DMORIENT_PORTRAIT else "Landscape" if devmode.dmOrientation == DMORIENT_LANDSCAPE else "Default",
                'color': "Color" if devmode.dmColor == DMCOLOR_COLOR else "Monochrome" if devmode.dmColor == DMCOLOR_MONOCHROME else "Default",
                'duplex': self._get_duplex_name(devmode.dmDuplex) if devmode.dmFields & DM_DUPLEX else "Default",
                'copies': devmode.dmCopies if devmode.dmFields & DM_COPIES else 1,
                'quality': devmode.dmPrintQuality if devmode.dmFields & DM_PRINTQUALITY else "Default",
                'tray': devmode.dmDefaultSource if devmode.dmFields & DM_DEFAULTSOURCE else "Default",
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting DEVMODE metadata: {e}")
            return {}
    
    def _get_paper_size_name(self, paper_size: int) -> str:
        """Convert paper size constant to human readable name"""
        paper_sizes = {
            1: "Letter", 2: "Letter Small", 3: "Tabloid", 4: "Ledger",
            5: "Legal", 6: "Statement", 7: "Executive", 8: "A3", 9: "A4",
            10: "A4 Small", 11: "A5", 12: "B4", 13: "B5", 14: "Folio",
            15: "Quarto", 16: "10x14", 17: "11x17", 18: "Note", 19: "Envelope #9",
            20: "Envelope #10", 21: "Envelope #11", 22: "Envelope #12",
            23: "Envelope #14", 24: "C Sheet", 25: "D Sheet", 26: "E Sheet",
            27: "Envelope DL", 28: "Envelope C5", 29: "Envelope C3",
            30: "Envelope C4", 31: "Envelope C6", 32: "Envelope C65",
            33: "Envelope B4", 34: "Envelope B5", 35: "Envelope B6",
            36: "Envelope", 37: "Envelope Monarch", 38: "Envelope Personal",
            39: "US Std Fanfold", 40: "German Std Fanfold", 41: "German Legal Fanfold"
        }
        return paper_sizes.get(paper_size, f"Custom ({paper_size})")
    
    def _get_duplex_name(self, duplex: int) -> str:
        """Convert duplex constant to human readable name"""
        duplex_names = {
            DMDUP_SIMPLEX: "Simplex",
            DMDUP_VERTICAL: "Duplex Vertical",
            DMDUP_HORIZONTAL: "Duplex Horizontal"
        }
        return duplex_names.get(duplex, f"Unknown ({duplex})")
    
    def apply_devmode_to_printer(self, printer_name: str, devmode_data: bytes) -> bool:
        """
        Apply DEVMODE configuration to printer using DocumentProperties.
        
        Args:
            printer_name: Name of the printer
            devmode_data: DEVMODE data to apply
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Open printer
            printer_handle = wintypes.HANDLE()
            if not self.winspool.OpenPrinterW(printer_name, byref(printer_handle), None):
                logger.error(f"Failed to open printer {printer_name}")
                return False
            
            try:
                # Create DEVMODE from data
                if len(devmode_data) < ctypes.sizeof(DEVMODE):
                    logger.error("Invalid DEVMODE data size")
                    return False
                
                devmode = DEVMODE.from_buffer_copy(devmode_data[:ctypes.sizeof(DEVMODE)])
                
                # Apply configuration using DocumentProperties
                # DM_MODIFY (8) = modify the printer's configuration
                result = self.winspool.DocumentPropertiesW(
                    None,                    # hwnd
                    printer_handle,          # hPrinter
                    printer_name,           # pDeviceName
                    None,                   # pDevModeOutput (not needed for modify)
                    byref(devmode),         # pDevModeInput
                    8                       # fMode (DM_MODIFY)
                )
                
                if result > 0:
                    logger.info(f"Successfully applied DEVMODE to {printer_name}")
                    return True
                else:
                    logger.error(f"DocumentProperties failed with result: {result}")
                    return False
                    
            finally:
                self.winspool.ClosePrinter(printer_handle)
                
        except Exception as e:
            logger.error(f"Error applying DEVMODE to printer: {e}")
            return False


# Global instance
win32_print_wrapper = Win32PrintDlgWrapper()