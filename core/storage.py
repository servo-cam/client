#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# This file is a part of servocam.org package <servocam.org>
# Created By: Marcin Szczygliński <info@servocam.org>
# GitHub: https://github.com/servo-cam
# License: MIT
# Updated At: 2023.03.27 02:00
# =============================================================================

import configparser
import os


class Storage:
    def __init__(self, worker=None):
        """
        Config storage handler

        :param worker: worker object
        """
        self.worker = worker
        self.config = None

        self.TYPE_STR = 0
        self.TYPE_INT = 1
        self.TYPE_FLOAT = 2
        self.TYPE_BOOL = 3

    def init(self):
        """Load config file"""
        if self.worker is None:
            return

        # load config
        self.worker.debug = self.get_cfg('client.debug', self.TYPE_BOOL)
        self.worker.server_ip = self.get_cfg('client.server.ip')  # args: --server-ip
        self.worker.web = self.get_cfg('client.web', self.TYPE_BOOL)  # args: --web
        self.worker.verbose = self.get_cfg('client.verbose', self.TYPE_BOOL)  # args: --verbose
        self.worker.silent = self.get_cfg('client.silent', self.TYPE_BOOL)  # args: --silent

        # client, host, devices
        self.worker.hostname = self.get_cfg('client.hostname')
        self.worker.client_ip = self.get_cfg('client.ip')
        self.worker.PORT_CONN = self.get_cfg('client.port.conn', self.TYPE_INT)
        self.worker.PORT_DATA = self.get_cfg('client.port.data', self.TYPE_INT)
        self.worker.PORT_WEB = self.get_cfg('client.port.web', self.TYPE_INT)
        self.worker.PORT_STATUS = self.get_cfg('client.port.status', self.TYPE_INT)
        self.worker.PORT_VIDEO = self.get_cfg('client.port.video', self.TYPE_INT)

        self.worker.device = self.get_cfg('client.device')
        self.worker.serial.BAUD_RATE = self.get_cfg('serial.baud_rate', self.TYPE_INT)

        # camera
        self.worker.use_pi_camera = self.get_cfg('client.camera.use_pi', self.TYPE_BOOL)  # args: --web
        self.worker.camera_idx = self.get_cfg('client.camera.idx', self.TYPE_INT)  # args: --camera
        self.worker.width = self.get_cfg('client.camera.width', self.TYPE_INT)  # args: --width
        self.worker.height = self.get_cfg('client.camera.height', self.TYPE_INT)  # args: --height

        # status check
        self.worker.status_check = self.get_cfg('client.status.check', self.TYPE_BOOL)
        self.worker.status_check_interval = self.get_cfg('client.status.interval', self.TYPE_INT)

        # security / encryption
        self.worker.encrypt.enabled_video = self.get_cfg('security.aes.video', self.TYPE_BOOL)
        self.worker.encrypt.enabled_data = self.get_cfg('security.aes.data', self.TYPE_BOOL)
        self.worker.encrypt.raw_key = self.get_cfg('security.aes.key')
        self.worker.web_token = self.get_cfg('security.web.token')
        if self.worker.web_token == '':
            self.worker.web_token = None

        # stream
        self.worker.jpg_compress = self.get_cfg('client.stream.jpeg', self.TYPE_BOOL)
        self.worker.jpg_quality = self.get_cfg('client.stream.jpeg.quality', self.TYPE_INT)
        self.worker.resize_width = self.get_cfg('client.stream.resize', self.TYPE_INT)

        # logging
        self.worker.logger.log_info = self.get_cfg('log.info.enabled', self.TYPE_BOOL)
        self.worker.logger.log_error = self.get_cfg('log.error.enabled', self.TYPE_BOOL)
        self.worker.logger.log_info_file = self.get_cfg('log.info.file')
        self.worker.logger.log_error_file = self.get_cfg('log.error.file')

        # socket
        self.worker.sockets.pull_wait = self.get_cfg('client.socket.pull.wait', self.TYPE_BOOL)
        self.worker.sockets.pull_linger = self.get_cfg('client.socket.pull.linger', self.TYPE_BOOL)
        self.worker.sockets.push_wait = self.get_cfg('client.socket.push.wait', self.TYPE_BOOL)
        self.worker.sockets.push_linger = self.get_cfg('client.socket.push.linger', self.TYPE_BOOL)

        # REQUIRED: auto-enable JPEG compression if encryption is enabled
        if self.worker.encrypt.enabled_video:
            self.worker.jpg_compress = True

    def get_cfg(self, key, astype=0):
        """Get config value

        :param key: config key
        :param astype: type of value
        :return: value
        """
        if self.config is None:
            self.config = configparser.ConfigParser()
            f = os.path.join('.', 'config.ini')
            if not os.path.exists(f):
                print("FATAL ERROR: config.ini not found!")
                return None
            self.config.read(f)

        if self.config.has_option("CONFIG", key):
            if astype == self.TYPE_STR:
                if str(self.config['CONFIG'][key]) == '' \
                        or self.config['CONFIG'][key] is None \
                        or str(self.config['CONFIG'][key]).lower() == 'none':
                    return None
                else:
                    return str(self.config['CONFIG'][key])
            elif astype == self.TYPE_BOOL:
                if str(self.config['CONFIG'][key]) == '' or self.config['CONFIG'][key] is None:
                    return False
                else:
                    return self.str2bool(self.config['CONFIG'][key])
            elif astype == self.TYPE_INT:
                if str(self.config['CONFIG'][key]) == '' or self.config['CONFIG'][key] is None:
                    return 0
                else:
                    return int(self.config['CONFIG'][key])
            elif astype == self.TYPE_FLOAT:
                if str(self.config['CONFIG'][key]) == '' or self.config['CONFIG'][key] is None:
                    return 0.0
                else:
                    return float(self.config['CONFIG'][key])
            else:
                return self.config['CONFIG'][key]
        else:
            if astype == self.TYPE_STR:
                return None
            elif astype == self.TYPE_BOOL:
                return False
            elif astype == self.TYPE_INT:
                return 0
            elif astype == self.TYPE_FLOAT:
                return 0.0

    def str2bool(self, val):
        """Convert string to bool

        :param val: string
        :return: bool
        """
        val = val.lower()
        if val in ('y', 'yes', 't', 'true', 'on', '1'):
            return True
        elif val in ('n', 'no', 'f', 'false', 'off', '0'):
            return False
        else:
            raise ValueError("Invalid bool value %r" % (val,))
