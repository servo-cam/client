#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# This file is a part of servocam.org package <servocam.org>
# Created By: Marcin Szczygliński <info@servocam.org>
# GitHub: https://github.com/servo-cam
# License: MIT
# Updated At: 2023.03.27 02:00
# =============================================================================

import logging
import traceback
from datetime import datetime


class Logger:
    LOG_STATUS = 1
    LOG_ERROR = 2
    LOG_WARNING = 3
    LOG_INFO = 4
    LOG_DEBUG = 5

    def __init__(self, worker=None):
        """
        Logger handler

        :param worker: worker object
        """
        self.worker = worker
        self.log_info = False
        self.log_error = True
        self.log_info_file = 'info.log'
        self.log_error_file = 'error.log'
        self.info_logger = None
        self.error_logger = None

    def init(self):
        """Prepare logger handlers"""
        formatter = logging.Formatter('%(asctime)s %(message)s')
        self.info_logger = logging.getLogger()
        self.error_logger = logging.getLogger()
        self.info_logger.setLevel(logging.INFO)
        self.error_logger.setLevel(logging.INFO)
        info_handler = logging.FileHandler(self.log_info_file)
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(formatter)
        error_handler = logging.FileHandler(self.log_error_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        self.info_logger.addHandler(info_handler)
        self.error_logger.addHandler(error_handler)

    def log(self, msg, level=LOG_INFO):
        """
        Log message to console and file

        :param msg: message to log
        :param level: log level
        """
        if self.worker.silent:
            return
        if level == self.LOG_STATUS or self.worker.verbose:
            if self.log_info:
                self.info_logger.info(msg)
            print(datetime.now().strftime('%H:%M:%S') + ": " + str(msg))

    def log_msg(self, prefix, msg, status=False):
        """
        Log message to console and file

        :param prefix: caller prefix
        :param msg: message to log
        :param status: if True, log as status message\
        """
        if prefix is not None:
            msg = "[" + prefix + "] " + str(msg)
        if status:
            self.log(msg, self.LOG_STATUS)
        else:
            self.log(msg)

    def log_err(self, prefix, err, msg=None):
        """
        Log error to console and file

        :param prefix: caller prefix
        :param err: exception object
        :param msg: error message
        """
        # error message
        if msg is not None:
            if prefix is not None:
                msg = "[" + prefix + "] " + str(msg)
            if self.log_error:
                self.error_logger.error(msg)
            if self.worker.verbose or self.worker.debug:
                print(datetime.now().strftime('%H:%M:%S') + ": " + str(msg))

        # debug / traceback
        if err is not None:
            if self.log_error:
                self.error_logger.error(err)
            if self.worker.debug:
                print(err)
                traceback.print_tb(err.__traceback__)
        if self.worker.debug:
            traceback.print_exc()
