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
import json
import time
import os
import io
import cv2
from core.storage import Storage

TRANSLATIONS = None
STORAGE = Storage()


def json_decode(data):
    """Decode json to dict

    :param data: json string
    :return: dict
    """
    try:
        return json.loads(data)
    except Exception as e:
        return None


def json_encode(data):
    """Encode dict to json

    :param data: dict
    :return: json string
    """
    return json.dumps(data)


def from_json(json_data, key='CMD'):
    """Load data from json

    :param json_data: json string
    :param key: key to search
    :return: value, timestamp
    """
    try:
        data = json.loads(json_data)
        timestamp = 0
        if 'k' in data and 'v' in data and data['k'] == key:
            if 't' in data:
                timestamp = data['t']
            return data['v'], timestamp
    except Exception as e:
        return None


def to_json(data, key='CMD'):
    """Convert data to json

    :param data: data to convert to json
    :param key: key to use
    :return: json encoded string
    """
    return json.dumps({'k': key, 'v': data, 't': round(time.time() * 1000)})


def trans(text):
    """Translate string

    :param text: string to translate
    :return: translated string
    """
    global TRANSLATIONS
    lang = STORAGE.get_cfg('app.lang')
    if TRANSLATIONS is None:
        TRANSLATIONS = configparser.ConfigParser()
        f = os.path.join('locale', lang + '.ini')
        data = io.open(f, mode="r", encoding="utf-8")
        TRANSLATIONS.read_string(data.read())
    if TRANSLATIONS.has_option("LOCALE", text):
        return TRANSLATIONS['LOCALE'][text]
    return text


def is_cv2():
    """Check if opencv version is 2

    :return: True if opencv version is 2, False otherwise
    """
    return opencv_version("2")


def is_cv3():
    """Check if opencv version is 3

    :return: True if opencv version is 3, False otherwise
    """
    return opencv_version("3")


def is_cv4():
    """Check if opencv version is 4

    :return: True if opencv version is 4, False otherwise
    """
    return opencv_version("4")


def opencv_version(version):
    """Check if opencv version is equal to version

    :param version: version to check
    :return: True if opencv version is equal to version, False otherwise
    """
    return cv2.__version__.startswith(version)
