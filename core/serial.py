#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# This file is a part of servocam.org package <servocam.org>
# Created By: Marcin Szczygliński <info@servocam.org>
# GitHub: https://github.com/servo-cam
# License: MIT
# Updated At: 2023.03.27 02:00
# =============================================================================

import serial
from serial.tools import list_ports  # pip install pyserial
from datetime import datetime
from core.utils import to_json


class Serial:
    LOG_PREFIX = "SERIAL"
    FORMAT_RAW = 'RAW'
    FORMAT_JSON = 'JSON'
    DATA_TYPE_CMD = 'cmd'
    CMD_STATUS = '0'
    END_CHAR = "\n"
    BAUD_RATE = 9600

    def __init__(self, worker=None):
        """
        Serial port handler

        :param worker: worker object
        """
        self.worker = worker
        self.port_in = None
        self.port_out = None
        self.serial_in = None  # external command input listen
        self.serial_out = None  # used for input and output from device
        self.is_send = False
        self.is_recv = False
        self.last_reset = datetime.now()
        self.sending = False
        self.sending_in = False
        self.last_status_check = datetime.now()
        self.status_check_interval = 3
        self.check_status = True
        self.disconnected_in = False
        self.disconnected_out = False

        # data format
        self.data_format = self.FORMAT_RAW

    def clear(self):
        """Close serial ports and clear data"""
        if self.serial_out is not None:
            if self.serial_out.is_open:
                self.serial_out.close()
                self.log('Serial (OUTPUT) port closed: ' + str(self.port_out), True)

        if self.serial_in is not None:
            if self.serial_in.is_open:
                self.serial_in.close()
                self.log('Serial (INPUT) port closed: ' + str(self.port_in), True)

        self.port_in = None
        self.port_out = None
        self.serial_in = None
        self.serial_out = None

    def get_ports(self):
        """Get list of available serial ports"""
        ports = []
        for port in list_ports.comports():
            ports.append(port.device)
        return ports

    def init(self):
        """
        Initialize serial ports

        Input port is used for receiving external commands
        Output port is used for sending commands to device and receiving data from device
        """
        if self.serial_out is None and self.port_out is not None:
            try:
                self.serial_out = serial.Serial(self.port_out, self.BAUD_RATE)
                # self.serial_out.timeout = 0.4
                self.log('Serial (OUTPUT) port opened: ' + str(self.port_out), True)
            except Exception as e:
                if not self.disconnected_out:
                    self.log_err(e, 'Serial (OUTPUT) initialize error (opened by other app?)')
                self.serial_out = None
                self.disconnected_out = True

    def init_input(self):
        """Initialize input serial port (used for receiving external commands)"""
        if self.serial_in is None and self.port_in is not None:
            try:
                self.serial_in = serial.Serial(self.port_in, self.BAUD_RATE)
                # self.serial_in.timeout = 0.4
                self.log('Serial (INPUT) port opened: ' + str(self.port_in), True)
            except Exception as e:
                if not self.disconnected_in:
                    self.log_err(e, 'Serial (INPUT) initialize error (opened by other app?)')
                self.serial_in = None
                self.disconnected_in = True

    def send(self, command):
        """
        Send raw command to device via output serial port

        :param command: raw command string to send
        """
        if self.port_out is None:
            return

        self.init()
        if self.serial_out is None:
            return

        if not self.serial_out.is_open:
            return
        try:
            # convert to json if needed
            if self.data_format == self.FORMAT_JSON:
                command = to_json(command, self.DATA_TYPE_CMD)

            # add end of command termination character
            command += self.END_CHAR
            self.sending = True
            self.serial_out.write(bytes(command, 'UTF-8'))
            self.sending = False
            self.is_send = True
        except Exception as e:
            self.serial_out.close()
            self.serial_out = None
            self.log_err(e, 'Serial (OUTPUT) data sending error')

    def send_input(self, command):
        """
        Send raw command to input serial port (used for receiving external commands)

        :param command: raw command string to send
        """
        if self.port_in is None:
            return

        self.init_input()
        if self.serial_in is None:
            return

        if not self.serial_in.is_open:
            return
        try:
            # convert to json if needed
            if self.data_format == self.FORMAT_JSON:
                command = to_json(command, self.DATA_TYPE_CMD)

            # add end of command termination character
            command += self.END_CHAR
            self.sending_in = True
            self.serial_in.write(bytes(command, 'UTF-8'))
            self.sending_in = False
            self.is_send = True
        except Exception as e:
            self.serial_in.close()
            self.serial_in = None
            self.log_err(e, 'Serial (INPUT) data sending error')

    def send_status_check(self):
        """Send status check command to device"""
        if self.sending:
            return

        # check only in specified seconds period
        if (datetime.now() - self.last_status_check).seconds > self.status_check_interval:
            self.send(self.CMD_STATUS)
            self.last_status_check = datetime.now()

    def update(self):
        """Called on update event (every frame) and sending status check command"""
        if self.port_out is None or self.serial_out is None or not self.serial_out.is_open:
            return

        if self.check_status:
            self.send_status_check()

    def listen_input(self):
        """
        Listen for messages from input serial port (used for receiving external commands)

        :return: received message (as UTF-8 string)
        """
        if self.port_in is None:
            return

        self.init_input()
        if self.serial_in is None:
            return

        if not self.serial_in.is_open:
            return

        try:
            buff = self.serial_in.readline().decode('utf-8')[:-2]
            self.is_recv = True
            return buff
        except Exception as e:
            self.serial_in.close()
            self.serial_in = None
            self.log_err(e, 'Serial (INPUT) listener error')

    def listen(self):
        """
        Listen for messages from output serial port

        :return: received message (as UTF-8 string)
        """
        if self.port_out is None:
            return

        self.init()
        if self.serial_out is None:
            return

        if not self.serial_out.is_open:
            return

        try:
            buff = self.serial_out.readline().decode('utf-8')[:-2]
            self.is_recv = True
            return buff
        except Exception as e:
            self.serial_out.close()
            self.serial_out = None
            self.log_err(e, 'Serial (OUTPUT) listener error')

    def reset_state(self):
        """Reset read and write state"""
        self.log('Serial reset state...', True)
        # wait a little before reset
        if (datetime.now() - self.last_reset).microseconds < 100000:
            return

        self.is_send = False
        self.is_recv = False
        self.last_reset = datetime.now()

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
