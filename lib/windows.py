import os

import win32api
import win32print

from lib import pdf


class Printing:
    def do_print(self, form):
        cwd = os.getcwd()
        pdf_file = pdf.generate(form)
        cmd_orientation = '-landscape' if form.get('orientation', '').lower() == 'landscape' else '-portrait'
        printer = form.get('printer')
        gspath = os.path.join(cwd, "bin", "ghostscript.exe")
        gsp_path = os.path.join(cwd, "bin", "gsprint.exe")
        win32api.ShellExecute(0, 'open', gsp_path,
                              f'-ghostscript "{gspath}" {cmd_orientation} -printer "{printer}" "{pdf_file}"', '.', 0)

    def get_printers(self):
        return [printer[2] for printer in (win32print.EnumPrinters(2) + win32print.EnumPrinters(4))]
