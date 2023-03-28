#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# This file is a part of servocam.org package <servocam.org>
# Created By: Marcin Szczygliński <info@servocam.org>
# GitHub: https://github.com/servo-cam
# License: MIT
# Updated At: 2023.03.27 02:00
# =============================================================================

import imagezmq
import zmq
import time
import simplejpeg
from imutils import resize
from imutils.video import VideoStream


class VideoPublisher:
    LOG_PREFIX = "VIDEO"

    def __init__(self, worker=None):
        """
        Video capture and publish handler

        :param worker: worker object
        """
        self.worker = worker
        self.sender = None
        self.stream = None
        self.frame = None
        self.restarting = False
        self.active = False
        self.exiting = False

    def setup(self):
        """Setup video stream"""
        resolution = None
        if self.worker.width is not None and self.worker.height is not None:
            if self.worker.width > 0 and self.worker.height > 0:
                resolution = (self.worker.width, self.worker.height)

        if resolution is not None:
            self.stream = VideoStream(usePiCamera=self.worker.use_pi_camera, resolution=resolution).start()
        else:
            self.stream = VideoStream(usePiCamera=self.worker.use_pi_camera).start()
        time.sleep(2.0)

    def make_sender(self):
        """Create ZMQ sender"""
        try:
            self.sender = imagezmq.ImageSender(
                connect_to="tcp://{}:{}".format(self.worker.server_ip, self.worker.PORT_VIDEO))
            self.sender.zmq_socket.setsockopt(zmq.RCVTIMEO, 2000)  # set a receive timeout
            self.sender.zmq_socket.setsockopt(zmq.SNDTIMEO, 2000)  # set a send timeout
            self.active = True
        except Exception as e:
            self.log_err(e, 'ZMQ sender create error')

    def close(self):
        """Close ZMQ sender"""
        if self.sender is not None:
            if not self.sender.zmq_context.closed:
                try:
                    self.sender.close()
                    self.sender.zmq_socket.close()
                except Exception as e:
                    self.log_err(e, 'ZMQ close error')

    def restart(self):
        """Restart ZMQ sender"""
        self.log('Restarting ZMQ sender', True)
        if not self.restarting:
            try:
                self.active = False
                self.restarting = True
                self.close()
                time.sleep(1)
                if self.sender.zmq_context.closed:
                    self.make_sender()
                time.sleep(1)
                self.restarting = False
            except Exception as e:
                self.log_err(e, 'ZMQ restart error')

    def start(self):
        """Start video stream"""
        self.make_sender()

    def stop(self):
        """Stop video stream"""
        self.exiting = True
        self.active = False
        if self.stream is not None:
            self.stream.stop()
        self.close()

    def destroy_context(self):
        """Destroy ZMQ context"""
        if self.sender is not None:
            try:
                self.sender.zmq_context.destroy()
            except Exception as e:
                self.log_err(e, 'ZMQ context destroy failed')

    def capture(self):
        """Capture frame"""
        while True:
            if self.exiting:
                break
            if self.stream is not None:
                self.frame = self.stream.read()

    def publish(self):
        """Publish frame via zmq"""
        while True:
            if self.worker.handler.do_restart:
                self.worker.handler.do_restart = False
                self.restart()

            if self.exiting:
                break
            if self.stream is not None:
                self.frame = self.stream.read()
            if self.sender is not None:
                self.send()

    def send(self):
        """Send frame via ZMQ"""
        if self.restarting or self.exiting or self.worker.server_ip is None:
            return

        try:
            # resize if needed
            if self.worker.resize_width is not None and self.worker.resize_width > 0:
                self.frame = resize(self.frame, width=self.worker.resize_width)

            timestamp = round(time.time() * 1000)

            # if JPEG compression
            if self.worker.jpg_compress:
                self.frame = simplejpeg.encode_jpeg(self.frame, quality=self.worker.jpg_quality, colorspace='BGR',
                                                    fastdct=True)

                # encrypt if needed
                if self.worker.encrypt.enabled_video:
                    self.frame = self.worker.encrypt.encrypt(self.frame, True)

                # send frame as JPEG, append timestamp after hostname
                self.sender.send_jpg(self.worker.hostname + '@' + str(timestamp), self.frame)
            else:
                # send frame as numpy image, append timestamp after hostname
                self.sender.send_image(self.worker.hostname + '@' + str(timestamp), self.frame)

            self.worker.connected = True

        # handle ZMQ errors
        except (zmq.ZMQError, zmq.ContextTerminated, zmq.Again) as e:
            self.restarting = True
            if self.active and self.sender is not None:
                # self.log_err(e, 'Closing ImageSender...')
                self.close()
                # self.log_err(e, 'Respawning ImageSender...')
                self.make_sender()
            self.restarting = False
            self.worker.connected = False

        # handle other errors
        except Exception as e:
            self.log_err(e, 'ZMQ send general error')
            self.worker.connected = False

    def log(self, msg, status=False):
        """Log message into console

        :param msg: string message
        :param status: if True then always show message
        """
        self.worker.logger.log_msg(self.LOG_PREFIX, msg, status)

    def log_err(self, err, msg=None):
        """Log error message into console

        :param err: exception
        :param msg: additional message
        """
        self.worker.logger.log_err(self.LOG_PREFIX, err, msg)
