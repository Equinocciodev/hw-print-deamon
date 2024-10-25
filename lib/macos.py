import os
from lib import pdf

class Printing(object):
    def do_print_old(self, form):
        self.do_print(form)

    def do_print(self, options):
        pdf_file = pdf.generate(options)

        if str(options.get('orientation')).lower() == 'landscape':
            cmd_orientation = '-o orientation-requested=4'
        else:
            cmd_orientation = ''
        command = f"lpr {cmd_orientation} -P {options.get('printer')} {pdf_file}"
        print(command)
        os.system(command)
