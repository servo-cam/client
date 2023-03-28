#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# This file is a part of servocam.org package <servocam.org>
# Created By: Marcin Szczygliński <info@servocam.org>
# GitHub: https://github.com/servo-cam
# License: MIT
# Updated At: 2023.03.27 02:00
# =============================================================================

import socket
import time
import zmq
from threading import Thread
from core.utils import json_decode, json_encode


class Sockets:
    LOG_PREFIX = "SOCKETS"
    MAX_CONN = 1
    CONN_BUFFER_SIZE = 1024

    def __init__(self, worker=None):
        """
        Sockets handler

        :param worker: worker object
        """
        self.worker = worker
        self.exiting = False
        self.pull_wait = False
        self.pull_linger = False
        self.push_wait = False
        self.push_linger = True

        self.conn = None  # self.socket_conn.accept()
        self.conn_socket = None  # socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.pull_context = None  # zmq.Context()
        self.pull_socket = None  # self.pull_context.socket(zmq.PULL)
        self.push_socket = None  # self.push_context.socket(zmq.PUSH)
        self.push_context = None  # zmq.Context()
        self.self_socket = None  # socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.self_context = None  # zmq.Context()

    def thread_connect(self):
        """Thread for handling connection initialize TCP socket"""
        ip = ''
        if self.worker.client_ip is not None and self.worker.client_ip != '*':
            ip = self.worker.client_ip
        self.conn_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.conn_socket.bind((ip, self.worker.PORT_CONN))
        self.conn_socket.listen(self.MAX_CONN)
        self.log(
            "Connection socket thread started on port {}. Listening for connection...".format(self.worker.PORT_CONN),
            True)

        while True:
            # on exit
            if self.exiting:
                break

            if self.conn_socket is None:
                continue

            try:
                # tcp, wait only for a connection from the server to get ip address
                self.conn, addr = self.conn_socket.accept()
                data = self.conn.recv(self.CONN_BUFFER_SIZE)
                msg = self.decode(data)
                if msg is not None and 'k' in msg and 'v' in msg and msg['k'] == self.worker.DATA_KEY_CONN:
                    if msg['v'] == self.worker.CMD_CONN_NEW:
                        self.worker.server_ip = addr[0]
                        self.log("Server connection from {}".format(addr[0]), True)
                        response = {
                            "k": self.worker.DATA_KEY_CMD,
                            "v": self.worker.RESPONSE_ACCEPT,
                            "t": round(time.time() * 1000),  # add timestamp
                            "hostname": self.worker.hostname  # return hostname
                        }
                        self.conn.sendall(self.encode(json_encode(response)))
                        self.worker.handler.handle_conn()  # empty handler

                        response = {
                            "k": self.worker.DATA_KEY_SELF,
                            "v": 'RESTART',
                        }
                        self.send_self(json_encode(response))

                # close connection and wait for another one
                self.conn.close()
                self.conn_socket.close()
                time.sleep(2)

                self.conn_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.conn_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.conn_socket.bind((ip, self.worker.PORT_CONN))
                self.conn_socket.listen(self.MAX_CONN)
            except Exception as e:
                self.log_err(e, 'Socket thread connect error')

                # close connection and wait for another one
                self.conn.close()
                self.conn_socket.close()
                time.sleep(2)

                # recreate socket on failure
                try:
                    self.conn_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.conn_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self.conn_socket.bind((ip, self.worker.PORT_CONN))
                    self.conn_socket.listen(self.MAX_CONN)
                except Exception as e:
                    self.log_err(e, 'Socket thread connect error')

    def thread_data(self):
        """
        Thread for handling data receive (PULL) and data send (PUSH) sockets

        Zmq data push (sender) socket - server app must connect to this socket via it's PULL socket
        Push socket is created here becose not thread safe
        """

        self.push_context = zmq.Context()
        self.push_socket = self.push_context.socket(zmq.PUSH)

        # push socket options
        if not self.push_wait:
            self.push_socket.setsockopt(zmq.CONFLATE,
                                        1)  # needed to avoid multiple messages in queue at use only latest
        if self.push_linger:
            self.push_socket.setsockopt(zmq.LINGER, 0)  # needed to avoid blocking on exit
        self.push_socket.bind("tcp://{}:{}".format(self.worker.client_ip, self.worker.PORT_STATUS))
        self.log("Sender (PUSH) socket started on port {}".format(self.worker.PORT_STATUS), True)

        self.pull_context = zmq.Context()
        self.pull_socket = self.pull_context.socket(zmq.PULL)

        # socket options
        if not self.pull_wait:
            self.pull_socket.setsockopt(zmq.CONFLATE,
                                        1)  # needed to avoid multiple messages in queue at use only latest
        if self.pull_linger:
            self.pull_socket.setsockopt(zmq.LINGER, 0)  # needed to avoid blocking on exit
        self.pull_socket.bind("tcp://{}:{}".format(self.worker.client_ip, self.worker.PORT_DATA))
        self.log("Data (PULL) socket thread started on port {}. Listening for data...".format(self.worker.PORT_DATA),
                 True)

        while True:
            # on exit
            if self.exiting:
                break

            # wait for server ip
            if self.worker.server_ip is None or self.pull_socket is None or self.pull_context is None or self.pull_context.closed:
                continue
            try:
                msg = self.pull_socket.recv()
                self.log("Received raw data via PULL socket: {}".format(msg))
                if msg is not None:
                    self.worker.handler.handle(self.decode(msg))
            except Exception as e:
                self.restart()
                self.log_err(e, 'Socket thread pull error')

    def decode(self, data):
        """
        Decode data received via socket

        :param data: received raw data to decode
        :return: decoded data (json)
        """
        # encrypt
        if self.worker.encrypt.enabled_data:
            return json_decode(self.worker.encrypt.decrypt(data))
        else:
            # raw
            return json_decode(data.decode("utf-8"))

    def encode(self, data):
        """
        Encode data to send via socket

        :param data: data to encode
        :return: encoded data (bytes)
        """
        # encrypt
        if self.worker.encrypt.enabled_data:
            return self.worker.encrypt.encrypt(data)
        else:
            # raw
            return bytes(data, 'UTF-8')

    def send_raw(self, msg):
        """
        Send raw data via push socket

        :param msg: data to send
        """
        if self.worker.server_ip is None or self.push_socket is None or self.push_context is None or self.push_context.closed:
            return
        try:
            self.log("Sending raw data via PUSH socket: {}".format(msg))
            self.push_socket.send(msg)
        except Exception as e:
            self.log_err(e, 'Socket send raw error')
            time.sleep(1)

    def send(self, msg):
        """
        Send data via push socket

        :param msg: data to send
        """
        if self.worker.server_ip is None or self.push_socket is None or self.push_context is None or self.push_context.closed:
            return
        try:
            self.log("Sending data via PUSH socket: {}".format(msg))
            self.push_socket.send(self.encode(msg))
        except Exception as e:
            self.log_err(e, 'Socket send error')
            time.sleep(1)

    def send_self(self, msg):
        """
        Send data to self via push socket

        :param msg: data to send
        """
        if self.self_socket is None or self.self_context is None or self.self_context.closed:
            return
        try:
            self.log("Sending loop data via self PUSH socket: {}".format(msg))
            self.self_socket.send(self.encode(msg))
        except Exception as e:
            self.log_err(e, 'Socket self send error')
            time.sleep(1)

    def restart_pull_socket(self):
        """Restart pull socket"""
        try:
            if self.pull_socket is not None:
                self.pull_socket.close()
            if self.pull_context is not None:
                self.pull_context.term()

            self.pull_socket = None
            time.sleep(1)

            self.pull_context = zmq.Context()
            self.pull_socket = self.pull_context.socket(zmq.PULL)

            # socket options
            if not self.pull_wait:
                self.pull_socket.setsockopt(zmq.CONFLATE,
                                            1)  # needed to avoid multiple messages in queue at use only latest
            if self.pull_linger:
                self.pull_socket.setsockopt(zmq.LINGER, 0)  # needed to avoid blocking on exit
            self.pull_socket.bind("tcp://{}:{}".format(self.worker.client_ip, self.worker.PORT_DATA))
        except Exception as e:
            self.log_err(e, 'Pull socket restarting error')

    def restart_push_socket(self):
        """Restart push socket"""
        try:
            if self.push_socket is not None:
                self.push_socket.close()
            if self.push_context is not None:
                self.push_context.term()

            self.push_socket = None
            time.sleep(1)

            self.push_context = zmq.Context()
            self.push_socket = self.push_context.socket(zmq.PUSH)
            # push socket options
            if not self.push_wait:
                self.push_socket.setsockopt(zmq.CONFLATE,
                                            1)  # needed to avoid multiple messages in queue at use only latest
            if self.push_linger:
                self.push_socket.setsockopt(zmq.LINGER, 0)  # needed to avoid blocking on exit
            self.push_socket.bind("tcp://{}:{}".format(self.worker.client_ip, self.worker.PORT_STATUS))
        except Exception as e:
            self.log_err(e, 'Push socket restarting error')

    def restart(self):
        """Restart both sockets"""
        self.restart_pull_socket()
        self.restart_push_socket()

    def stop(self):
        """Stop both sockets"""
        self.log("Stopping all sockets...", True)
        self.exiting = True
        try:
            if self.push_socket is not None:
                self.push_socket.close()
            if self.push_context is not None:
                self.push_context.term()
            if self.conn is not None:
                self.conn.close()
            if self.conn_socket is not None:
                self.conn_socket.close()
            if self.pull_socket is not None:
                self.pull_socket.close()
            if self.pull_context is not None:
                self.pull_context.term()
        except Exception as e:
            self.log_err(e, 'Socket stopping error')

    def start(self):
        """Start sockets and threads"""

        # tcp connect socket thread (receive)
        conn = Thread(target=self.thread_connect, args=())
        conn.daemon = True
        conn.start()

        # zmq data pull socket thread (receive)
        data = Thread(target=self.thread_data, args=())
        data.daemon = True
        data.start()

        time.sleep(1)
        while self.pull_socket is None:
            time.sleep(1)

        # create self push socket
        self.self_context = zmq.Context()
        self.self_socket = self.self_context.socket(zmq.PUSH)
        self.self_socket.connect("tcp://{}:{}".format('127.0.0.1', self.worker.PORT_DATA))
        self.log("Loop sender (PUSH) socket connected to self port {}".format(self.worker.PORT_DATA), True)

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
