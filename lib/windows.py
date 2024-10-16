import win32api
import win32print
from lib import pdf

class Printing(object):
    def print(self,printer_data, orientation, printer):
        pdf_file = pdf.generate(printer_data, orientation)
        #rotated_pdf_file = rotatepdf.rotate_pdf(pdf_file)
        win32print.SetDefaultPrinter(printer)
        win32api.ShellExecute(0, "print", pdf_file, None, ".", 0)



    def get_printers(self):
        return win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL, None, 1)