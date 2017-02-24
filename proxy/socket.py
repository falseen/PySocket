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


# make a new socket class
class new_socket(socket.socket):

    def __init__(self, *args, **kwds):
        super(new_socket, self).__init__(*args, **kwds)
        # new_self_method(self, 'sendto', new_sendto)
        # new_self_method(self, 'recvfrom', new_recvfrom)
        self._is_proxy = False


# replace socket class to new_socket
socket.socket = new_socket


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
        self = args[1]
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


def _SOCKS5_request(self, dst_addr, dst_port):
    logging.debug("send socks5 hello")
    self.send(SOCKS5_REQUEST_DATA)
    recv_data = self.recv(BUF_SIZE)
    if recv_data == b"\x05\x00":
        logging.debug("recv socks5 hello %s" % binascii.hexlify(recv_data))
    else:
        logging.debug("not socks5 proxy %s" % binascii.hexlify(recv_data))
        pass
    socks5_cmd = struct.pack(">B", self.type)
    dst_port_b = struct.pack('>H', dst_port)
    dst_addr_b = pack_addr(dst_addr)
    header_data = b"\x05" + socks5_cmd + b"\x00" + dst_addr_b + dst_port_b
    logging.debug("send socks5 header %s:%d" % (dst_addr, dst_port))
    self.send(header_data)
    recv_data = self.recv(BUF_SIZE)
    if recv_data[1] == b"\x00":
        logging.debug("recv socks5 header %s" %
                      binascii.hexlify(recv_data))
    else:
        logging.debug("connect socks5 proxy faild %s" %
                      binascii.hexlify(recv_data))


# 处理send ，此处为实例方法
def new_send(real_method, self, *args, **kwds):
    return_value = real_method(*args, **kwds)
    return return_value


def new_sendto(real_method, self, *args, **kwds):
    data, dst_addrs = args
    dst_addr, dst_port = dst_addrs
    if dst_port == 53:
        self._is_proxy = True
        UDP_SOCKS5_HEADER = b"\x00\x00\x00"
        new_dst_addr = "8.8.8.8"
        dst_addr_b = pack_addr(new_dst_addr)
        dst_port_b = struct.pack('>H', dst_port)
        send_data = UDP_SOCKS5_HEADER + dst_addr_b + dst_port_b + data
        PROXY_ADDRS = (PROXY_ADDR, PROXY_PORT)
        new_args = args[2:]
        logging.debug("send udp socks5 data to %s:%d" %
                      (PROXY_ADDR, PROXY_PORT))
        return_value = real_method(send_data, PROXY_ADDRS, *new_args, **kwds)
    else:
        return_value = real_method(*args, **kwds)
    return return_value


def new_recvfrom(real_method, self, *args, **kwds):
    return_value = real_method(*args, **kwds)
    if self._is_proxy:
        data, addr = return_value
        print("data", binascii.hexlify(data))
        return_value = (data, addr)

        logging.debug("recv udp socks5 data from %s:%d" %
                      (PROXY_ADDR, PROXY_PORT))
    return return_value


def new_recv(real_method, self, *args, **kwds):
    return_value = real_method(*args, **kwds)
    return return_value


# 处理connect，此处为类方法
@set_self_blocking
def new_connect(real_method, self, *args, **kwds):

    if self.type == 1:
        dst_addr, dst_port = args[0]
        real_connect = real_method
        PROXY_ADDRS = (PROXY_ADDR, PROXY_PORT)
        new_args = args[1:]
        logging.info("connect dst %s:%d use proxy %s:%d" %
                     (dst_addr, dst_port, PROXY_ADDR, PROXY_PORT))
        try:
            real_connect(self, PROXY_ADDRS, *new_args, **kwds)
        except socket.error as ERROR:
            logging.error("%s Connt connect to proxy %s:%d" %
                          (ERROR, PROXY_ADDR, PROXY_PORT))
            raise
        else:
            _SOCKS5_request(self, dst_addr, dst_port)
    elif self.type == 3:
        # UDP TODO
        pass
    else:
        return_value = real_method(self, *args, **kwds)


new_class_method(socket.socket, 'connect', new_connect)
