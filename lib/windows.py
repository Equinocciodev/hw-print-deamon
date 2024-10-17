import win32api
import win32print
import psutil
import time
from lib import pdf

class Printing(object):
    def print(self,printer_data, orientation, printer):
        pdf_file = pdf.generate(printer_data, orientation)
        print(printer)
        win32print.SetDefaultPrinter(printer)
        
        printer_handle = win32print.OpenPrinter(printer)
        printer_info = win32print.GetPrinter(printer_handle, 2)
        devmode = printer_info['pDevMode']
        
        # rundll32 printui.dll,PrintUIEntry /e /n "EPSON LX-350 ESC/P" # Usar en caso de emergecia
        if orientation == 'landscape':
            devmode.PaperSize = 75  # "Fanfold 11 x 8 1/2 in"
        elif orientation == 'portrait':
            devmode.PaperSize = 1 # "Letter"
            
        try:
            win32print.SetPrinter(printer_handle, 2, printer_info, 0)
        except:
            pass
        
        win32print.ClosePrinter(printer_handle)
        win32api.ShellExecute(0, "print", pdf_file, None, ".", 0)
        
        time.sleep(8)
        
        self.close_adobe_reader()

    def get_printers(self):
        return win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL, None, 1)
    
    def close_adobe_reader(self):
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'Acrobat.exe' in proc.info['name']:
                proc.terminate()
                proc.wait(timeout=8) 