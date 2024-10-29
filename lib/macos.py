import os
import subprocess

from lib import pdf


class Printing:
    def do_print(self, options):
        pdf_file = pdf.generate(options)
        cmd_orientation = '-o orientation-requested=4' if options.get('orientation', '').lower() == 'landscape' else ''
        command = f"lpr {cmd_orientation} -P {options.get('printer')} {pdf_file}"
        print(command)
        os.system(command)

    def get_printers(self):
        result = subprocess.run(['lpstat', '-p'], stdout=subprocess.PIPE)
        return [line.split()[1] for line in result.stdout.decode().splitlines() if line]
