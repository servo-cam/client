#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# This file is a part of servocam.org package <servocam.org>
# Created By: Marcin Szczygliński <info@servocam.org>
# GitHub: https://github.com/servo-cam
# License: MIT
# Updated At: 2023.03.27 02:00
# =============================================================================

import argparse
import sys
import traceback
from core.worker import Worker

if __name__ == '__main__':
    # parse args
    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--device", required=False,
                    help="device (arduino or raspberry)")
    ap.add_argument("-p", "--pi", required=False,
                    help="use Pi camera (CSI)")
    ap.add_argument("-c", "--camera", required=False,
                    help="camera index")
    ap.add_argument("-x", "--width", required=False,
                    help="camera capture resolution (width)")
    ap.add_argument("-y", "--height", required=False,
                    help="camera capture resolution (height)")
    ap.add_argument("-i", "--ip", required=False,
                    help="Client IP address")
    ap.add_argument("-s", "--server-ip", required=False,
                    help="ip address of the server to which the client will connect")
    ap.add_argument("-w", "--web", required=False,
                    help="web streaming")
    ap.add_argument("-v", "--verbose", required=False,
                    help="verbose mode")
    ap.add_argument("-n", "--hidden", required=False,
                    help="hidden / silent mode")
    ap.add_argument("-u", "--status", required=False,
                    help="Check device status")
    ap.add_argument("-e", "--debug", required=False,
                    help="Debug mode")
    args = vars(ap.parse_args())

    # start client worker
    worker = Worker()

    try:
        worker.init(args)
        worker.start()
    except KeyboardInterrupt:
        worker.stop()
        print('Exiting...')
        sys.exit(0)
    except Exception as e:
        worker.stop()
        print('Error: ' + str(e))
        traceback.print_exc()
        sys.exit(1)
