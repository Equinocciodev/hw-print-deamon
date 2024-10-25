import win32api
import win32print
import os
import psutil
import time
from lib import pdf

class Printing(object):
    def do_print_old(self,form):
        pdf_file = pdf.generate(form)
        printer=form.get('printer')
        win32print.SetDefaultPrinter(printer)
        
        printer_handle = win32print.OpenPrinter(printer)
        printer_info = win32print.GetPrinter(printer_handle, 2)
        devmode = printer_info['pDevMode']
        
        # rundll32 printui.dll,PrintUIEntry /e /n "EPSON LX-350 ESC/P" # Usar en caso de emergecia
        devmode.PaperSize = 1 #letter
        if str(form.get('orientation')).lower() == 'landscape':
            devmode.PaperSize = 75
        try:
            win32print.SetPrinter(printer_handle, 2, printer_info, 0)
        except:
            pass
        
        win32print.ClosePrinter(printer_handle)
        win32api.ShellExecute(0, "print", pdf_file, None, ".", 0)
        
        time.sleep(8)
        
        self.close_adobe_reader()

    def do_print(self,form):
        current_working_directory = os.getcwd()
        pdf_file = pdf.generate(form)
        cmd_orientation = '-portrait'
        if str(form.get('orientation')).lower() == 'landscape':
            cmd_orientation='-landscape'
        printer=form.get('printer')
        gspath = os.path.join(current_working_directory, "bin", "ghostscript.exe")
        gsp_path = os.path.join(current_working_directory, "bin", "gsprint.exe")
        win32api.ShellExecute(0, 'open', gsp_path,
                              '-ghostscript "' + gspath + '" '+cmd_orientation+ ' -printer "' + printer + '" "%s"' % (pdf_file), '.', 0)



    
    def close_adobe_reader(self):
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and proc.info['name'] in ('Acrobat.exe'):
                proc.terminate()
                proc.wait(timeout=8)