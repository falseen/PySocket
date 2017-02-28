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



#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# 原始地址和端口
orgin_addr = "114.114.114.114"
orgin_port = 53

# 修改后的地址和端口
new_dst_addr = "114.114.115.115"
new_dst_port = 53

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++



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
    info = sys.version_info
    if info[0] >= 3:
        setattr(self, method_name, types.MethodType(lambda *args, **kwds: new_method(method, *args, **kwds), self))
    else:
        setattr(self, method_name, types.MethodType(lambda *args, **kwds: new_method(method, *args, **kwds), self, self))


def new_recvfrom(real_method, self, *args, **kwds):
    data, src_addrs = real_method(*args, **kwds)
    src_addr, src_port = src_addrs
    if src_port == new_dst_port and src_addr == new_dst_addr:
        # logging.info("fix %s:%d to %s:%d" % (src_addr, src_port, orgin_addr, orgin_port))
        return data, (orgin_addr, orgin_port)
    return data, src_addrs


def new_sendto(orgin_method ,self, *args, **kwds):
    data, dst_addrs = args
    dst_addr, dst_port = dst_addrs
    if dst_port == orgin_port and dst_addr == orgin_addr :
        # logging.info("forward %s:%d to %s:%d" % (dst_addr, dst_port, new_dst_addr, new_dst_port))
        new_self_method(self, 'recvfrom', new_recvfrom)
        args = (data, (new_dst_addr, new_dst_port))
    return_value = orgin_method(*args, **kwds)
    return return_value


# make a new socket class
class new_socket(socket.socket):

    def __init__(self, *args, **kwds):
        super(new_socket, self).__init__(*args, **kwds)
        new_self_method(self, 'sendto', new_sendto)
        


# replace socket class to new_socket
socket.socket = new_socket
