import os
import subprocess

from lib import pdf


class Printing(object):
    
    def print(self, printer_data, printer):
        pdf_file = pdf.generate(printer_data)
        command="lpr -P " + printer + " " + pdf_file
        os.system(command)

    def get_printers(self):
        return subprocess.getoutput("lpstat -a | awk '{print $1}'").split("\n")
