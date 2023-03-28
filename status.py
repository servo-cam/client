#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# This file is a part of servocam.org package <servocam.org>
# Created By: Marcin Szczygliński <info@servocam.org>
# GitHub: https://github.com/servo-cam
# License: MIT
# Updated At: 2023.03.27 02:00
# =============================================================================

from datetime import datetime


class Status:
    def __init__(self, worker=None):
        self.worker = worker

    def init(self):
        """Initialize device

        This method is called when device is initialized and ready to work
        """
        pass

    def get_status(self):
        """Get device status

        This method is called every X seconds to get device status and send it to the server
        """
        # self.worker.serial_status <--- current status received from serial port
        return "STATUS: " + datetime.now().strftime("%H:%M:%S")
