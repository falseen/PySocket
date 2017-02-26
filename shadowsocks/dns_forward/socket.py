#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2017 Falseen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from __future__ import absolute_import, division, print_function, \
    with_statement, nested_scopes

import sys

del sys.modules['socket']

import sys
import time
import logging
import types
import functools

path = sys.path[0]
sys.path.pop(0)

# import real socket
import socket
import struct
import binascii

sys.path.insert(0, path)


PROXY_TYPE = "socks5"
PROXY_ADDR = "127.0.0.1"
PROXY_PORT = 1080
SOCKS5_REQUEST_DATA = b"\x05\x01\x00"
BUF_SIZE = 32 * 1024


def to_bytes(s):
    if bytes != str:
        if type(s) == str:
            return s.encode('utf-8')
    return s


def to_str(s):
    if bytes != str:
        if type(s) == bytes:
            return s.decode('utf-8')
    return s


def pack_addr(address):
    address_str = to_str(address)
    address = to_bytes(address)
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            r = socket.inet_pton(family, address_str)
            if family == socket.AF_INET6:
                return b'\x04' + r
            else:
                return b'\x01' + r
        except (TypeError, ValueError, OSError, IOError):
            pass
    if len(address) > 255:
        address = address[:255]  # TODO
    return b'\x03' + chr(len(address)) + address



# 动态patch类方法
def new_class_method(_class, method_name, new_method):
    method = getattr(_class, method_name)
    info = sys.version_info
    if info[0] >= 3:
        setattr(_class, method_name,
                types.MethodType(lambda *args, **kwds: new_method(method, *args, **kwds), _class))
    else:
        setattr(_class, method_name,
                types.MethodType(lambda *args, **kwds: new_method(method, *args, **kwds), None, _class))


# 动态patch实例方法
def new_self_method(self, method_name, new_method):
    method = getattr(self, method_name)
    setattr(self, method_name, types.MethodType(lambda *args, **
                                                kwds: new_method(method, *args, **kwds), self, self))


def set_self_blocking(function):

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        self = args[0]
        try:
            _is_blocking = self.gettimeout()
            # if not blocking then set blocking
            if _is_blocking == 0:
                self.setblocking(True)
            return function(*args, **kwargs)
        except Exception as e:
            print(e)
            raise
        finally:
            # set orgin blcoking
            if _is_blocking == 0:
                self.setblocking(False)
    return wrapper


# make a new socket class
class new_socket(socket.socket):

    def __init__(self, *args, **kwds):
        super(new_socket, self).__init__(*args, **kwds)
        # new_self_method(self, 'sendto', new_sendto)
        # new_self_method(self, 'recvfrom', new_recvfrom)

    def sendto(real_method, self, *args, **kwds):
        data, dst_addrs = args
        dst_addr, dst_port = dst_addrs
        if dst_port == 53:
            self._is_proxy = True
            UDP_SOCKS5_HEADER = b"\x00\x00\x00"
            new_dst_addr = "8.8.8.8"
            new_dst_port = 53
            args = (data, (new_dst_addr, new_dst_port))
        return_value = super(new_socket, self).sendto(*args, **kwds)
        return return_value
        


# replace socket class to new_socket
socket._socketobject = new_socket
print(" replace socket class to new_socket")
