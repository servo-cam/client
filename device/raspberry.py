#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# This file is a part of servocam.org package <servocam.org>
# Created By: Marcin Szczygliński <info@servocam.org>
# GitHub: https://github.com/servo-cam
# License: MIT
# Updated At: 2023.03.27 02:00
# =============================================================================

import RPi.GPIO as GPIO
import time
from datetime import datetime
from threading import Thread
from core.utils import from_json


class Raspberry:
    LOG_PREFIX = "DEVICE: RASPBERRY"

    FREQUENCY_X = 50
    FREQUENCY_Y = 50
    ANGLE_START_X = 90
    ANGLE_START_Y = 90
    ANGLE_MIN_X = 0
    ANGLE_MAX_X = 180
    ANGLE_MIN_Y = 0
    ANGLE_MAX_Y = 180
    LIMIT_MIN_X = 0
    LIMIT_MAX_X = 180
    LIMIT_MIN_Y = 0
    LIMIT_MAX_Y = 180
    CYCLE_START_X = 0
    CYCLE_START_Y = 0
    CYCLE_MIN_X = 2.5
    CYCLE_MAX_X = 12.5
    CYCLE_MIN_Y = 2.5
    CYCLE_MAX_Y = 12.5
    DELAY_X = 0.02
    DELAY_Y = 0.02
    DELAY_ACTION = 0
    USE_LIMIT = False

    MODE_INPUT_SERIAL = 'serial'
    MODE_INPUT_NETWORK = 'network'
    MODE_OUTPUT_SERIAL = 'serial'
    MODE_OUTPUT_GPIO = 'gpio'

    def __init__(self, worker=None):
        """
        Raspberry device handler

        :param worker: worker object
        """
        self.worker = worker
        self.args = None
        self.sending = False
        self.servo_x = None
        self.servo_y = None
        self.initialized = False
        self.exiting = False
        self.prev_status = None
        self.is_x = False
        self.is_y = False
        self.pins = {}  # GPIO pins configuration
        self.mode_input = self.MODE_INPUT_NETWORK  # serial|network
        self.mode_output = self.MODE_OUTPUT_SERIAL  # serial|gpio

    def collect_status(self):
        """Collect device status"""
        if self.worker is not None:
            self.worker.status = self.worker.status_callback.get_status()
            if self.worker.status != self.prev_status:
                if not self.worker.web and self.worker.connected:
                    self.worker.socket_send_self(self.worker.status)
            self.prev_status = self.worker.status

    def send(self, command):
        """
        Send command to device

        :param command: command to send
        """
        if self.exiting:
            return

        if command is None or command == "":
            return

        if self.mode_output == self.MODE_OUTPUT_SERIAL:
            self.send_serial(command)
        elif self.mode_output == self.MODE_OUTPUT_GPIO:
            self.send_gpio(command)

    def send_serial(self, command):
        """
        Send command to device via serial

        :param command: command to send
        """
        self.worker.serial.send(command)

    def send_gpio(self, command):
        """
        Send command to device via GPIO

        :param command: command to send
        """
        # begin GPIO mode if enabled
        if not self.initialized:
            self.cmd_init()

        cmds = command.split(",")
        n = 0
        for cmd in cmds:
            if n == 0:
                self.cmd_servo_x(int(cmd))
            elif n == 1:
                self.cmd_servo_y(int(cmd))
            elif n == 2:
                pass  # counter
            elif n == 3:
                self.cmd_action("A1", bool(int(cmd)))
            elif n == 4:
                self.cmd_action("A2", bool(int(cmd)))
            elif n == 5:
                self.cmd_action("A3", bool(int(cmd)))
            elif n == 6:
                self.cmd_action("B4", bool(int(cmd)))
            elif n == 7:
                self.cmd_action("B5", bool(int(cmd)))
            elif n == 8:
                self.cmd_action("B6", bool(int(cmd)))
            n += 1

        self.log("SENDING TO GPIO: " + str(command))

    def cmd_init(self):
        """Reset and prepare device"""
        # set GPIO numbering mode
        GPIO.setmode(GPIO.BOARD)
        if not self.worker.debug:
            GPIO.setwarnings(False)

        # set GPIO pins to output
        GPIO.setup(self.pins['SERVO_X'], GPIO.OUT)
        GPIO.setup(self.pins['SERVO_Y'], GPIO.OUT)
        GPIO.setup(self.pins['A1'], GPIO.OUT)
        GPIO.setup(self.pins['A2'], GPIO.OUT)
        GPIO.setup(self.pins['A3'], GPIO.OUT)
        GPIO.setup(self.pins['B4'], GPIO.OUT)
        GPIO.setup(self.pins['B5'], GPIO.OUT)
        GPIO.setup(self.pins['B6'], GPIO.OUT)

        # 50Hz frequency
        self.servo_x = GPIO.PWM(self.pins['SERVO_X'], self.FREQUENCY_X)
        self.servo_y = GPIO.PWM(self.pins['SERVO_Y'], self.FREQUENCY_Y)

        self.servo_x.start(0)  # start with 0 duty cycle
        self.servo_y.start(0)  # start with 0 duty cycle

        # set all to initial state
        self.cmd_servo_x(self.ANGLE_START_X)  # center
        self.cmd_servo_y(self.ANGLE_START_Y)  # center
        self.cmd_action("A1", False)
        self.cmd_action("A2", False)
        self.cmd_action("A3", False)
        self.cmd_action("B4", False)
        self.cmd_action("B5", False)
        self.cmd_action("B6", False)

        self.initialized = True

    def cmd_servo_x(self, angle):
        """
        Send servo x command
        :param angle: angle to send
        """
        if self.is_x:
            return
        self.is_x = True

        # check angle limit
        if angle < self.LIMIT_MIN_X:
            if self.LIMIT_MIN_X is not None:
                angle = self.LIMIT_MIN_X
        elif angle > self.LIMIT_MAX_X:
            if self.LIMIT_MAX_X is not None:
                angle = self.LIMIT_MAX_X

        # prepare cycle
        if self.USE_LIMIT:
            # using min/max limit
            cycle = self.CYCLE_MIN_X + (angle / (self.LIMIT_MAX_X - self.LIMIT_MIN_X)) * (
                    self.CYCLE_MAX_X - self.CYCLE_MIN_X)
        else:
            # using min/max angle
            cycle = self.CYCLE_MIN_X + (angle / (self.ANGLE_MAX_X - self.ANGLE_MIN_X)) * (
                    self.CYCLE_MAX_X - self.CYCLE_MIN_X)

        self.log("SERVO X: {} (PIN {} {})".format(angle, self.pins['SERVO_X'], cycle))
        self.servo_x.ChangeDutyCycle(cycle)
        if self.DELAY_X is not None and self.DELAY_X > 0:
            self.log("DELAY X: " + str(self.DELAY_X))
            time.sleep(self.DELAY_X)
        self.is_x = False

    def cmd_servo_y(self, angle):
        """
        Send servo y command

        :param angle: angle to send
        """
        if self.is_y:
            return
        self.is_y = True

        # check angle limit
        if angle < self.LIMIT_MIN_Y:
            if self.LIMIT_MIN_Y is not None:
                angle = self.LIMIT_MIN_Y
        elif angle > self.LIMIT_MAX_Y:
            if self.LIMIT_MAX_Y is not None:
                angle = self.LIMIT_MAX_Y

        # prepare cycle
        if self.USE_LIMIT:
            # using min/max limit
            cycle = self.CYCLE_MIN_Y + (angle / (self.LIMIT_MAX_Y - self.LIMIT_MIN_Y)) * (
                    self.CYCLE_MAX_Y - self.CYCLE_MIN_Y)
        else:
            # using min/max angle
            cycle = self.CYCLE_MIN_Y + (angle / (self.ANGLE_MAX_Y - self.ANGLE_MIN_Y)) * (
                    self.CYCLE_MAX_Y - self.CYCLE_MIN_Y)

        self.log("SERVO Y: {} (PIN {} {})".format(angle, self.pins['SERVO_Y'], cycle))
        self.servo_y.ChangeDutyCycle(cycle)
        if self.DELAY_Y is not None and self.DELAY_Y > 0:
            self.log("DELAY Y: " + str(self.DELAY_Y))
            time.sleep(self.DELAY_Y)
        self.is_y = False

    def cmd_action(self, action, value):
        """
        Send action command to device

        :param action: action name
        :param value: action state (bool)
        """
        pin = self.pins[action]
        if value:
            GPIO.output(pin, GPIO.HIGH)
            self.log("ACTION ON: {} (PIN {}, {})".format(action, pin, value))
        else:
            GPIO.output(pin, GPIO.LOW)
            self.log("ACTION OFF: {} (PIN {}, {})".format(action, pin, value))

        if self.DELAY_ACTION is not None and self.DELAY_ACTION > 0:
            self.log("DELAY_PIN: " + str(self.DELAY_ACTION))
            time.sleep(self.DELAY_ACTION)

    def device_send(self, cmd):
        """
        Send command to device

        :param cmd: command to send
        """
        self.sending = True
        self.send(cmd)
        self.sending = False

    def get_status(self):
        """Get current device status"""
        return self.worker.status

    def serial_output_thread(self):
        """Serial output (device) listener thread"""
        while True:
            if self.exiting:
                break

            buff = self.worker.serial.listen()  # listen connected device
            if buff is not None and buff != "":
                if self.worker.serial.data_format == self.worker.FORMAT_JSON:
                    buff = from_json(buff, self.worker.DATA_TYPE_CMD)
                if self.mode_input == self.MODE_INPUT_SERIAL:
                    self.worker.serial.send_input(buff)  # re-send up to connected server
                self.worker.serial_status = buff

    def serial_input_thread(self):
        """Serial input (server, controller) listener thread"""
        while True:
            if self.exiting:
                break

            buff = self.worker.serial.listen_input()  # listen commands from connected server
            if buff is not None and buff != "":
                if self.worker.serial.data_format == self.worker.FORMAT_JSON:
                    buff = from_json(buff, self.worker.DATA_TYPE_CMD)
                self.device_send(buff)

    def status_check_thread(self):
        """Status check thread"""
        while True:
            if self.exiting:
                break

            # check only in specified seconds period
            if (datetime.now() - self.worker.last_status_check).seconds > self.worker.status_check_interval:
                # send status check command to serial port and wait for response in another thread
                self.collect_status()
                self.worker.last_status_check = datetime.now()
                time.sleep(1.0)

    def load_config(self):
        """Load pins config and rest params from config file"""
        # servo config
        self.pins['SERVO_X'] = self.worker.storage.get_cfg('client.device.raspberry.pin.servo_x',
                                                           self.worker.storage.TYPE_INT)
        self.pins['SERVO_Y'] = self.worker.storage.get_cfg('client.device.raspberry.pin.servo_y',
                                                           self.worker.storage.TYPE_INT)

        # action config
        self.pins['A1'] = self.worker.storage.get_cfg('client.device.raspberry.pin.action_A1',
                                                      self.worker.storage.TYPE_INT)
        self.pins['A2'] = self.worker.storage.get_cfg('client.device.raspberry.pin.action_A2',
                                                      self.worker.storage.TYPE_INT)
        self.pins['A3'] = self.worker.storage.get_cfg('client.device.raspberry.pin.action_A3',
                                                      self.worker.storage.TYPE_INT)
        self.pins['B4'] = self.worker.storage.get_cfg('client.device.raspberry.pin.action_B4',
                                                      self.worker.storage.TYPE_INT)
        self.pins['B5'] = self.worker.storage.get_cfg('client.device.raspberry.pin.action_B5',
                                                      self.worker.storage.TYPE_INT)
        self.pins['B6'] = self.worker.storage.get_cfg('client.device.raspberry.pin.action_B6',
                                                      self.worker.storage.TYPE_INT)

        self.DELAY_ACTION = self.worker.storage.get_cfg('client.device.raspberry.pin.action.delay',
                                                        self.worker.storage.TYPE_FLOAT)

        # mode and serial ports
        self.mode_input = self.worker.storage.get_cfg('client.device.raspberry.mode.input')
        self.mode_output = self.worker.storage.get_cfg('client.device.raspberry.mode.output')
        self.worker.serial.port_in = self.worker.storage.get_cfg('client.device.raspberry.serial.input')
        self.worker.serial.port_out = self.worker.storage.get_cfg('client.device.raspberry.serial.output')
        self.worker.serial.data_format = self.worker.storage.get_cfg('client.device.raspberry.data_format')

        # servo parameters
        self.FREQUENCY_X = self.worker.storage.get_cfg('servo.freq.x', self.worker.storage.TYPE_INT)
        self.FREQUENCY_Y = self.worker.storage.get_cfg('servo.freq.y', self.worker.storage.TYPE_INT)
        self.ANGLE_START_X = self.worker.storage.get_cfg('servo.angle.start.x', self.worker.storage.TYPE_INT)
        self.ANGLE_START_Y = self.worker.storage.get_cfg('servo.angle.start.y', self.worker.storage.TYPE_INT)
        self.ANGLE_MIN_X = self.worker.storage.get_cfg('servo.angle.min.x', self.worker.storage.TYPE_INT)
        self.ANGLE_MAX_X = self.worker.storage.get_cfg('servo.angle.max.x', self.worker.storage.TYPE_INT)
        self.ANGLE_MIN_Y = self.worker.storage.get_cfg('servo.angle.min.y', self.worker.storage.TYPE_INT)
        self.ANGLE_MAX_Y = self.worker.storage.get_cfg('servo.angle.max.y', self.worker.storage.TYPE_INT)
        self.LIMIT_MIN_X = self.worker.storage.get_cfg('servo.limit.min.x', self.worker.storage.TYPE_INT)
        self.LIMIT_MAX_X = self.worker.storage.get_cfg('servo.limit.max.x', self.worker.storage.TYPE_INT)
        self.LIMIT_MIN_Y = self.worker.storage.get_cfg('servo.limit.min.y', self.worker.storage.TYPE_INT)
        self.LIMIT_MAX_Y = self.worker.storage.get_cfg('servo.limit.max.y', self.worker.storage.TYPE_INT)
        self.CYCLE_START_X = self.worker.storage.get_cfg('servo.cycle.start.x', self.worker.storage.TYPE_FLOAT)
        self.CYCLE_START_Y = self.worker.storage.get_cfg('servo.cycle.start.y', self.worker.storage.TYPE_FLOAT)
        self.CYCLE_MIN_X = self.worker.storage.get_cfg('servo.cycle.min.x', self.worker.storage.TYPE_FLOAT)
        self.CYCLE_MAX_X = self.worker.storage.get_cfg('servo.cycle.max.x', self.worker.storage.TYPE_FLOAT)
        self.CYCLE_MIN_Y = self.worker.storage.get_cfg('servo.cycle.min.y', self.worker.storage.TYPE_FLOAT)
        self.CYCLE_MAX_Y = self.worker.storage.get_cfg('servo.cycle.max.y', self.worker.storage.TYPE_FLOAT)
        self.DELAY_X = self.worker.storage.get_cfg('servo.delay.x', self.worker.storage.TYPE_FLOAT)
        self.DELAY_Y = self.worker.storage.get_cfg('servo.delay.y', self.worker.storage.TYPE_FLOAT)

    def set_args(self, args=None):
        """
        Set args from command line

        :param args: args from command line
        """
        if args is not None:
            self.args = args

    def init(self):
        """Initiate worker"""
        # load pins config
        self.load_config()

        # log
        self.log("Input mode: " + self.mode_input, True)
        self.log("Output mode: " + self.mode_output, True)
        self.log("Serial input port: " + str(self.worker.serial.port_in), True)
        self.log("Serial output port: " + str(self.worker.serial.port_out), True)

    def start(self):
        """Start worker"""
        # reset all pins
        if self.mode_output == self.MODE_OUTPUT_GPIO:
            self.cmd_init()

        # if connection to device with serial port (e.g. Arduino at output connected)
        if self.mode_output == self.MODE_OUTPUT_SERIAL and self.worker.serial.port_out is not None:
            # start thread for serial command to device re-sending
            self.log("Starting serial output thread...", True)
            serial_thread = Thread(target=self.serial_output_thread, args=())
            serial_thread.daemon = True
            serial_thread.start()

        # if input connection from server with serial (e.g. PC with USB at input connected)
        if self.mode_input == self.MODE_INPUT_SERIAL and self.worker.serial.port_in is not None:
            # start thread for serial command receive
            self.log("Starting serial input thread...", True)
            serial_input_thread = Thread(target=self.serial_input_thread, args=())
            serial_input_thread.daemon = True
            serial_input_thread.start()

        # if status checking is enabled
        if self.worker.status_check:
            # start thread for in interval status check
            self.log("Starting status check thread...", True)
            status_thread = Thread(target=self.status_check_thread, args=())
            status_thread.daemon = True
            status_thread.start()

        self.worker.status_callback.init()  # init callback

    def cleanup(self):
        """Cleanup resources"""
        # GPIO cleanup
        if self.initialized and self.mode_output == self.MODE_OUTPUT_GPIO:
            self.log("Cleaning GPIO...", True)
            self.servo_x.stop()
            self.servo_y.stop()
            GPIO.cleanup()

        # serial ports cleanup
        if self.mode_output == self.MODE_OUTPUT_SERIAL or self.mode_input == self.MODE_INPUT_SERIAL:
            self.log("Cleaning serial ports...", True)
            self.worker.serial.clear()

    def stop(self):
        """Stop worker"""
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
