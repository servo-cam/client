#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# This file is a part of servocam.org package <servocam.org>
# Created By: Marcin Szczygliński <info@servocam.org>
# GitHub: https://github.com/servo-cam
# License: MIT
# Updated At: 2023.03.27 02:00
# =============================================================================

import os
from core.utils import to_json


class Handler:
    LOG_PREFIX = "HANDLER"

    def __init__(self, worker=None):
        """
        Events handling main class

        :param worker: worker object
        """
        self.worker = worker
        self.do_restart = False

    def handle(self, msg):
        """
        Handle JSON encoded message

        :param msg: JSON encoded message
        """
        self.log("Handling JSON: {}".format(msg))
        if msg is not None:
            if 'k' in msg and 'v' in msg:
                if msg['k'] == self.worker.DATA_KEY_CMD:
                    self.handle_cmd(msg['v'])
                elif msg['k'] == self.worker.DATA_KEY_SELF:  # resend to server
                    self.handle_self(msg['v'])

    def handle_conn(self):
        """Handle on connection message"""
        pass

    def handle_self(self, cmd):
        """
        Handle self (device loop) message

        :param cmd: command string
        """
        if cmd == 'RESTART':
            self.log("Restarting sockets...")
            self.do_restart = True  # signal to restart video, direct restart is not allowed - not thread safe
            # self.worker.video.destroy_context()  # TODO: is context destroy here thread safe?
            self.worker.sockets.restart()  # same thread, restart sockets allowed - thread safe here
        else:
            self.worker.socket_send(cmd)

    def handle_cmd(self, cmd):
        """
        Handle command message

        :param cmd: command decoded from JSON
        """
        self.log("Handling CMD: {}".format(cmd))
        if cmd == self.worker.CMD_DISCONNECT:
            self.log("Disconnecting...", True)
            self.worker.sockets.send(to_json(self.worker.RESPONSE_OK, self.worker.DATA_KEY_CMD))
            self.worker.connected = False
        elif cmd == self.worker.CMD_RESTART:
            self.log("Restarting...", True)
            self.worker.sockets.send(to_json(self.worker.RESPONSE_OK, self.worker.DATA_KEY_CMD))
            self.worker.video.do_restart = True
        elif cmd == self.worker.CMD_DESTROY:
            self.worker.sockets.send(to_json(self.worker.RESPONSE_OK, self.worker.DATA_KEY_CMD))
            self.log("Destroying...", True)
            self.worker.stop()
            os._exit(0)  # quit app
        else:
            # to device command sending is here
            if cmd != "":
                self.worker.sockets.send(to_json(self.worker.RESPONSE_RECV, self.worker.DATA_KEY_CMD))
                self.worker.send_to_device(cmd)
                self.log("DEVICE CMD SENT OK: {}".format(cmd))

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
