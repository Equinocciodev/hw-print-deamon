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