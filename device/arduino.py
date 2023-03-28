#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# This file is a part of servocam.org package <servocam.org>
# Created By: Marcin Szczygliński <info@servocam.org>
# GitHub: https://github.com/servo-cam
# License: MIT
# Updated At: 2023.03.27 02:00
# =============================================================================

import time
from datetime import datetime
from threading import Thread
from core.utils import from_json


class Arduino:
    LOG_PREFIX = "DEVICE: ARDUINO"

    def __init__(self, worker=None):
        """
        Arduino device handler

        :param worker: worker object
        """
        self.worker = worker
        self.args = None
        self.status = None
        self.sending = False
        self.exiting = False
        self.prev_status = None

    def collect_status(self):
        """Collect device status"""
        if self.worker is not None:
            self.worker.status = self.worker.status_callback.get_status()
            if self.worker.status != self.prev_status:
                if not self.worker.web and self.worker.connected:
                    self.worker.socket_send_self(self.worker.status)
            self.prev_status = self.worker.status

    def send(self, cmd):
        """Send command to device via serial port"""
        if self.exiting:
            return

        self.worker.serial.send(cmd)

    def device_send(self, cmd):
        """
        Send command to device

        :param cmd: command to send (string)
        """
        if self.exiting:
            return

        self.sending = True
        self.send(cmd)
        self.sending = False

    def get_status(self):
        """Get device status"""
        return self.worker.status

    def status_thread(self):
        """Collect device status in interval"""
        while True:
            if self.exiting:
                break

            if self.sending:
                time.sleep(1.0)
                continue

            # check only in specified seconds period
            if (datetime.now() - self.worker.last_status_check).seconds > self.worker.status_check_interval:
                # send status check command to serial port and wait for response in another thread
                self.collect_status()
                self.worker.last_status_check = datetime.now()
                time.sleep(1.0)

    def serial_thread(self):
        """Listener for serial port data"""
        while True:
            if self.exiting:
                break

            buff = self.worker.serial.listen()
            if buff is not None and buff != "":
                if self.worker.serial.data_format == self.worker.FORMAT_JSON:
                    buff = from_json(buff, self.worker.DATA_TYPE_CMD)
                self.worker.serial_status = buff

    def set_args(self, args=None):
        """
        Set console arguments

        :param args: console arguments
        """
        if args is not None:
            self.args = args

    def init(self):
        """Initialize device"""
        # load device config
        self.worker.serial.data_format = self.worker.storage.get_cfg('client.device.arduino.data_format')
        self.worker.serial.port_out = self.worker.storage.get_cfg('client.device.arduino.serial')

        # log
        self.log("Serial port: " + self.worker.serial.port_out, True)

    def start(self):
        """Start device"""
        if self.worker.status_check:
            # start thread for serial command re-sending
            serial_thread = Thread(target=self.serial_thread, args=())
            serial_thread.daemon = True
            serial_thread.start()

            # start thread for in interval status check
            status_thread = Thread(target=self.status_thread, args=())
            status_thread.daemon = True
            status_thread.start()

        self.worker.status_callback.init()  # init callback

    def cleanup(self):
        """Cleanup resources"""
        self.worker.serial.clear()

    def stop(self):
        """Stop threads"""
        self.exiting = True
        self.cleanup()

    def log(self, msg, status=False):
        """
        Log message into console

        :param msg: string message
        :param status: if True then always show message
        """
        self.worker.logger.log_msg(self.LOG_PREFIX, msg, status)

    def log_err(self, err, msg=None):
        """
        Log error message into console

        :param err: exception
        :param msg: additional message
        """
        self.worker.logger.log_err(self.LOG_PREFIX, err, msg)
