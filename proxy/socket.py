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

path = sys.path[0]
sys.path.pop(0)

import socket    # 导入真正的socket包

sys.path.insert(0, path)

import struct
import binascii

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


# 动态path类方法
def new_class_method(_class, method_name, new_method):
    method = getattr(_class, method_name)
    info = sys.version_info
    if info[0] >= 3:
        setattr(_class, method_name,
                types.MethodType(lambda *args, **kwds: new_method(method, *args, **kwds), _class))
    else:
        setattr(_class, method_name,
                types.MethodType(lambda *args, **kwds: new_method(method, *args, **kwds), None, _class))

# 动态path实例方法


def new_self_method(self, method_name, new_method):
    method = getattr(self, method_name)
    setattr(self, method_name, types.MethodType(lambda *args, **
                                                kwds: new_method(method, *args, **kwds), self, self))

# 处理send ，此处为实例方法


def new_send(real_method, self, *args, **kwds):
    data = args[0]
    fd = self.fileno()
    self_id = "%d_%d" % (id(self), fd)
    if self.type == 1:
        socks_stage = self._fd_to_self.get(self_id)["socks_stage"]
        if socks_stage != "stream":
            self.setblocking(True)
            dst_addr, dst_port = self._fd_to_self.get(self_id)["dst_addrs"]
            logging.debug("send socks5 hello")
            real_method(SOCKS5_REQUEST_DATA)
            recv_data = self.recv(BUF_SIZE)
            if recv_data == b"\x05\x00":
                logging.debug("recv socks5 hello %s" % binascii.hexlify(recv_data))
            else:
                # TODO
                logging.debug("not socks5 proxy %s" % binascii.hexlify(recv_data))
                pass
            socks_type = self.type
            socks5_cmd = struct.pack(">B", socks_type)
            dst_port_b = struct.pack('>H', dst_port)
            dst_addr_b = pack_addr(dst_addr)
            header_data = b"\x05" + socks5_cmd + b"\x00" + dst_addr_b + dst_port_b
            logging.debug("send socks5 header %s:%d" % (dst_addr, dst_port))
            real_method(header_data)
            recv_data = self.recv(BUF_SIZE)
            if recv_data[1] == b"\x00":
                logging.debug("recv socks5 header %s" % binascii.hexlify(recv_data))
            else:
                # TODO
                logging.debug("connect socks5 proxy faild %s" % binascii.hexlify(recv_data))
                pass
            self._fd_to_self.get(self_id)["socks_stage"] = "stream"
            self.setblocking(False)
            return_value = real_method(data)
            return return_value
    elif self.type == 3:
        # UDP TODO
        pass
    return_value = real_method(*args, **kwds)
    return return_value


def new_recv(real_method, self, *args, **kwds):
    BUF_SIZE = args[0]
    self_id = id(self)
    fd = self.fileno()
    remote_addrs = self.getsockname()
    return_value = real_method(*args, **kwds)
    return return_value


# 处理connect，此处为类方法
def new_connect(real_method, self, *args, **kwds):
    dst_addr, dst_port = args[0]
    fd = self.fileno()
    self_id = "%d_%d" % (id(self), fd)
    self._fd_to_self.update({self_id: {"dst_addrs": (dst_addr, dst_port),
                                       "socks_stage": "init",
                                       }
                             })
    logging.info("connect dst %s:%d use proxy %s:%d" % (dst_addr, dst_port, PROXY_ADDR, PROXY_PORT))
    new_self_method(self, 'send', new_send)
    # new_self_method(self, 'sendto', new_send)
    PROXY_ADDRS = (PROXY_ADDR, PROXY_PORT)
    return_value = real_method(self, PROXY_ADDRS, **kwds)

setattr(socket.socket, '_fd_to_self', {})
new_class_method(socket.socket, 'connect', new_connect)
