import os

import win32api

from lib import pdf


class Printing(object):

    def do_print(self,form):
        cwd = os.getcwd()
        pdf_file = pdf.generate(form)
        cmd_orientation = '-portrait'
        if str(form.get('orientation')).lower() == 'landscape':
            cmd_orientation='-landscape'
        printer=form.get('printer')
        gspath = os.path.join(cwd, "bin", "ghostscript.exe")
        gsp_path = os.path.join(cwd, "bin", "gsprint.exe")
        win32api.ShellExecute(0, 'open', gsp_path,
                              '-ghostscript "' + gspath + '" '+cmd_orientation+ ' -printer "' + printer + '" "%s"' % (pdf_file), '.', 0)

