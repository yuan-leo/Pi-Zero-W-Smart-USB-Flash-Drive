#!/usr/bin/python3
"""One bounded printer snapshot, serialized as real JSON."""
import json
from usb_share_common import query, read_flag


def get_status():
    data = dict(ip_address=read_flag('printer_ip'), printer_model=read_flag('printer_model'),
                connection='Not Connected', files='', printer_status='', print_job='',
                layers_complete='', percent_complete='', seconds_remaining=0, resin_required='')
    try:
        files, status = query(['getfiles', 'getstatus'])
        fields = status.split(',')
        if len(fields) < 3 or fields[0] != 'getstatus' or fields[1] not in ('print', 'pause', 'stop'):
            raise ValueError('Invalid status response')
        data['files'] = files
        data['printer_status'] = {'print': 'Printing', 'pause': 'Paused', 'stop': 'Stopped'}[fields[1]]
        if fields[1] == 'print':
            if len(fields) < 10:
                raise ValueError('Incomplete print status')
            data.update(print_job=fields[2], percent_complete=fields[4] + '%',
                        layers_complete=fields[5] + ' / ' + fields[3],
                        seconds_remaining=int(fields[7]), resin_required=fields[8])
        data['connection'] = 'Connected'
    except (OSError, ValueError, IndexError):
        pass
    return data


if __name__ == '__main__':
    print(json.dumps(get_status()))
