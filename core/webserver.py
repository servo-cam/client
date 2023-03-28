#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# This file is a part of servocam.org package <servocam.org>
# Created By: Marcin Szczygliński <info@servocam.org>
# GitHub: https://github.com/servo-cam
# License: MIT
# Updated At: 2023.03.27 02:00
# =============================================================================

from threading import Lock, Thread
import logging
import click
import simplejpeg
from flask import Flask, Response, request, abort
from imutils import resize
from core.utils import to_json


class Webserver:
    LOG_PREFIX = "WEBSERVER"

    def __init__(self, worker):
        """
        Webserver handler

        :param worker: worker object
        """
        self.worker = worker
        self.exiting = False
        self.lock = None
        self.app = None

    def web_has_access(self):
        """Check if request has access token"""
        if self.worker.web_token is None:
            return True

        args = request.args
        token = args.get("token")
        if token is not None and token == self.worker.web_token:
            return True
        return False

    def web_cmd(self):
        """Handle command from web interface"""
        # check access at first
        if not self.web_has_access():
            abort(403)

        # get cmd from request
        data = request.form
        cmd = data.get('cmd')

        # send to device
        if cmd is not None and cmd != "":
            self.worker.send_to_device(cmd)

        if self.worker.debug:
            self.log(str(cmd))

        if self.worker.status is not None:
            status = to_json(self.worker.get_status())
        else:
            status = self.worker.RESPONSE_OK

        response = Response(status)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    def web_video_feed(self):
        """Video streaming route handler"""
        # check access at first
        if not self.web_has_access():
            abort(403)

        response = Response(self.web_generate(),
                            mimetype="multipart/x-mixed-replace; boundary=frame")
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    def web_status(self):
        """Get status from device route handler"""
        # check access at first
        if not self.web_has_access():
            abort(403)

        response = Response(str(self.worker.get_status()))
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    def web_generate(self):
        """Video streaming generate"""
        while True:
            if self.exiting:
                break

            # with self.lock:
            if self.worker.video.frame is None:
                continue

            # resize if needed
            if self.worker.resize_width is not None and self.worker.resize_width > 0:
                frame = resize(self.worker.video.frame, width=self.worker.resize_width)
                frame = simplejpeg.encode_jpeg(frame, quality=self.worker.jpg_quality,
                                               colorspace='BGR',
                                               fastdct=True)
            else:
                frame = simplejpeg.encode_jpeg(self.worker.video.frame, quality=self.worker.jpg_quality,
                                               colorspace='BGR',
                                               fastdct=True)

            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
                   bytearray(frame) + b'\r\n')

    def init(self):
        """Initialize webserver"""

        # create lock for thread-safe video streaming
        # self.lock = Lock()

        # disable logger output if not verbose
        if not self.worker.verbose:
            # disable flask logging
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)

            def secho(text, file=None, nl=None, err=None, color=None, **styles):
                pass

            def echo(text, file=None, nl=None, err=None, color=None, **styles):
                pass

            click.echo = echo
            click.secho = secho

        # routes
        self.app = Flask(__name__)
        self.app.add_url_rule('/', 'video', self.web_video_feed)
        self.app.add_url_rule('/cmd', 'cmd', self.web_cmd, methods=['GET', 'POST'])
        self.app.add_url_rule('/status', 'status', self.web_status)

    def start(self):
        """Start webserver"""
        self.init()

        # start webserver thread
        thread = Thread(target=self.webserver_thread, args=())
        thread.daemon = True
        thread.start()

        # start video capture loop
        self.worker.video.capture()

    def webserver_thread(self):
        """Webserver thread"""
        ip = '0.0.0.0'
        if self.worker.client_ip is not None and self.worker.client_ip != '' and self.worker.client_ip != '*':
            ip = self.worker.client_ip

        # start the flask app
        self.app.run(host=ip, port=self.worker.PORT_WEB, debug=self.worker.debug,
                     threaded=True, use_reloader=False)

    def stop(self):
        """Stop webserver"""
        self.log("Stopping webserver...", True)
        self.exiting = True

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
