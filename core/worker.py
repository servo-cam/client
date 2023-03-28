#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# This file is a part of servocam.org package <servocam.org>
# Created By: Marcin Szczygliński <info@servocam.org>
# GitHub: https://github.com/servo-cam
# License: MIT
# Updated At: 2023.03.27 02:00
# =============================================================================

import re
import time
import socket
from datetime import datetime
from core.utils import json_encode
from core.video import VideoPublisher
from core.sockets import Sockets
from core.storage import Storage
from core.serial import Serial
from core.handler import Handler
from core.encrypt import Encrypt
from core.logger import Logger
from core.webserver import Webserver
from device.arduino import Arduino
from status import Status  # <---- status callback


class Worker:
    AUTHOR = "servocam.org"
    EMAIL = "info@servocam.org"
    TIME_WAIT = 2.0

    # devices
    DEVICE_ARDUINO = 'arduino'
    DEVICE_RASPBERRY = 'raspberry'

    # data formats
    FORMAT_RAW = 'RAW'
    FORMAT_JSON = 'JSON'

    # commands
    CMD_PING = '1'
    CMD_STATUS = '0'
    CMD_CONN_NEW = 'NEW'
    CMD_CONNECT = 'CONNECT'
    CMD_RESTART = 'RESTART'
    CMD_DESTROY = 'DESTROY'
    CMD_DISCONNECT = 'DISCONNECT'

    # response codes
    RESPONSE_OK = 'OK'
    RESPONSE_ACCEPT = 'ACCEPT'
    RESPONSE_RECV = 'RECV'
    RESPONSE_PONG = '1'

    # data types keys
    DATA_KEY_CMD = 'CMD'
    DATA_KEY_SELF = 'SELF'
    DATA_KEY_CONN = 'CONN'

    # ports
    PORT_VIDEO = 5555
    PORT_DATA = 6666
    PORT_CONN = 6667
    PORT_STATUS = 6668
    PORT_WEB = 8888

    def __init__(self):
        """
        Main worker class
        """
        self.args = None
        self.version = "0.0.0"
        self.build = "0"
        self.debug = True
        self.verbose = False
        self.silent = False
        self.connected = False
        self.device = self.DEVICE_ARDUINO
        self.logger = Logger(self)
        self.handler = Handler(self)
        self.video = VideoPublisher(self)
        self.sockets = Sockets(self)
        self.storage = Storage(self)
        self.serial = Serial(self)
        self.encrypt = Encrypt()
        self.status_callback = Status(self)
        self.webserver = Webserver(self)
        self.arduino = Arduino(self)
        self.raspberry = None
        self.server_ip = None
        self.client_ip = "*"
        self.hostname = None
        self.web = False
        self.web_token = None
        self.camera_idx = 0
        self.use_pi_camera = False
        self.jpg_compress = False
        self.jpg_quality = 80
        self.resize_width = None
        self.width = None
        self.height = None
        self.use_capture = False
        self.status_check = False
        self.status_check_interval = 5
        self.status = None
        self.serial_status = None
        self.last_status_check = datetime.now()

        # load config.ini
        self.storage.init()
        self.logger.init()

    def init(self, args=None):
        """
        Initialize client

        :param args: console arguments (dict)
        """
        self.parse_args(args)

        # get hostname
        if self.hostname is None or self.hostname == "":
            self.hostname = socket.gethostname()

        self.load_version()
        self.log("Servo Cam client starting...")
        self.log("Version: " + str(self.version) + " Build: " + str(self.build))
        self.log("(c) 2023 " + str(self.AUTHOR) + " <" + str(self.EMAIL) + ">")
        self.log("------------------------")
        self.log("Debug: {}".format(self.debug))
        self.log("Verbose: {}".format(self.verbose))
        self.log("Status check: {}".format(self.status_check))
        self.log("Status check interval: {}".format(self.status_check_interval))
        self.log("Camera index: {}".format(self.camera_idx))
        self.log("Use Pi camera: {}".format(self.use_pi_camera))
        self.log("Web: {}".format(self.web))
        self.log("Client IP: {}".format(self.client_ip))
        self.log("Device: " + str(self.device))

        # init device worker
        if self.device == self.DEVICE_ARDUINO:
            self.arduino.init()
            self.arduino.set_args(args)
        elif self.device == self.DEVICE_RASPBERRY:
            # import here to avoid import errors on other devices
            from device.raspberry import Raspberry
            self.raspberry = Raspberry(self)
            self.raspberry.init()
            self.raspberry.set_args(args)

        # init camera
        self.video.setup()

    def parse_args(self, args=None):
        """
        Parse console arguments

        :param args: console arguments (dict)
        """
        if args is not None:
            self.args = args
            if 'device' in self.args and self.args['device'] is not None:
                self.device = self.args['device']
            if 'server-ip' in self.args and self.args['server-ip'] is not None:
                self.server_ip = self.args['server-ip']
            if 'client-ip' in self.args and self.args['client-ip'] is not None:
                self.client_ip = self.args['client-ip']
            if 'web' in self.args and self.args['web'] is not None:
                self.web = bool(int(self.args['web']))
            if 'verbose' in self.args and self.args['verbose'] is not None:
                self.verbose = bool(int(self.args['verbose']))
            if 'hidden' in self.args and self.args['hidden'] is not None:
                self.silent = bool(int(self.args['hidden']))
            if 'status' in self.args and self.args['status'] is not None:
                self.status_check = bool(int(self.args['status']))
            if 'pi' in self.args and self.args['pi'] is not None:
                self.use_pi_camera = bool(int(self.args['pi']))
            if 'camera' in self.args and self.args['camera'] is not None:
                self.camera_idx = int(self.args['camera'])
            if 'width' in self.args and self.args['width'] is not None:
                self.width = int(self.args['width'])
            if 'height' in self.args and self.args['height'] is not None:
                self.height = int(self.args['height'])
            if 'debug' in self.args and self.args['debug'] is not None:
                self.debug = bool(int(self.args['debug']))

            # if debug enable all
            if self.debug:
                self.verbose = True
                self.silent = False

    def send_to_device(self, cmd):
        """
        Send command to device

        :param cmd: command to send
        """
        if self.device == self.DEVICE_ARDUINO:
            self.arduino.device_send(cmd)
        elif self.device == self.DEVICE_RASPBERRY:
            self.raspberry.device_send(cmd)

    def socket_send(self, msg):
        """
        Send command to server via socket

        :param msg: command to send
        """
        data = {
            "k": self.DATA_KEY_CMD,
            "v": msg,
            "t": round(time.time() * 1000)
        }
        self.sockets.send(json_encode(data))

    def socket_send_self(self, msg):
        """
        Send command to self (loop socket)

        :param msg: command to send to self via loop socket
        """
        data = {
            "k": self.DATA_KEY_SELF,
            "v": msg,
            "t": round(time.time() * 1000)
        }
        self.sockets.send_self(json_encode(data))

    def get_status(self):
        """
        Get device status

        :return: device status
        """
        if self.device == self.DEVICE_ARDUINO:
            return self.arduino.get_status()
        elif self.device == self.DEVICE_RASPBERRY:
            return self.raspberry.get_status()

    def start_device(self):
        """Start device worker"""
        # start device worker
        if self.device == self.DEVICE_ARDUINO:
            self.arduino.start()
        elif self.device == self.DEVICE_RASPBERRY:
            self.raspberry.start()

    def start(self):
        """Start client"""
        if not self.web:
            self.sockets.start()
            self.log("Waiting for server IP...")
            while self.server_ip is None:
                time.sleep(0.1)

            self.log("Starting device worker: {}".format(self.device))
            self.start_device()
            self.video.start()  # init video stream
            self.log("Starting sending video to {}".format(self.server_ip))
            self.video.publish()  # serve via zmq
        else:
            self.log("Starting device worker: {}".format(self.device))
            self.start_device()
            self.log("Starting web server on port {}".format(self.PORT_WEB))
            self.webserver.start()  # serve via web

    def stop(self):
        """Stop client and clean up"""
        self.sockets.stop()
        self.video.stop()
        if self.device == self.DEVICE_RASPBERRY:
            self.raspberry.stop()
        elif self.device == self.DEVICE_ARDUINO:
            self.arduino.stop()
        if self.web:
            self.webserver.stop()

    def load_version(self):
        """Read version info from __init__.py"""
        try:
            self.version = re.search(r'{}\s*=\s*[\'"]([^\'"]*)[\'"]'.format("__version__"),
                                     open('./__init__.py').read()).group(1)
            self.build = re.search(r'{}\s*=\s*[\'"]([^\'"]*)[\'"]'.format("__build__"),
                                   open('./__init__.py').read()).group(1)
        except Exception as e:
            self.logger.log_err(e, None, 'Error reading version file: __init__.py')
            self.version = "0.0.0"
            self.build = "0"

    # log message
    def log(self, msg, status=True):
        """
        Log message

        :param msg: message to log
        :param status: True if log as status message
        """
        if status:
            self.logger.log_msg(None, msg, self.logger.LOG_STATUS)
        else:
            self.logger.log_msg(None, msg)
