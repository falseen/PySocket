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
#
# 功能：限制客户端数量（基于ip判断）
#
# 使用说明：1.将此文件放在程序根目录中即可生效，不用做其他设置（需要重新运行程序）。
#          2.修改 recv_timeout 和 limit_clients_num 为你想要的数值。
#          3.如果你的服务器有ipv6或有多个ip,并且你想让这些ip分开限制，则可以设置 only_port 为 False 。
#
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

# import real socket
import socket    

sys.path.insert(0, path)


#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

set_close_timeout = False   # 是否清理指定时间内无数据收发的连接，仅对TCP有效，socket会自动关闭正常或异常断开的连接, 所以一般不用设置。
                            #   如果为True则根据下面的超时时间进行清理，如果为 False 则根据socket的超时时间来清理(5分钟左右)。

recv_timeout = 4000            # 设置 tcp 清理连接的超时时间，单位毫秒（1000毫秒等于一分钟）。
                               #    在此时间内无连接或无数据 接收 的连接会被清理。只针对 tcp，从测试来看，似乎没什么作用。

recvfrom_timeout = 60       # 设置 udp 清理连接的超时时间，单位秒。在此时间内无连接或无数据 接收 的连接会被清理。只针对 udp。
limit_clients_num = 1       # 设置每个端口的允许通过的ip数量，即客户端的ip数量
only_port = True            # 设置是否只根据端口判断。如果为 True ，则只根据端口判断。如果为 False ，则会严格的根据服务端ip+端口进行判断

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++



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


# 处理Tcp连接
def new_accept(orgin_method, self, *args, **kwds):

    while True:
        return_value = orgin_method(self, *args, **kwds)
        self_socket = return_value[0]
        client_ip, client_port = return_value[1]
        server_addrs = self._server_addrs
        client_list = self._all_client_list.get(server_addrs, {})
        if len(client_list) < limit_clients_num or client_ip in client_list:
            self_socket._server_addrs = self._server_addrs
            self_socket.close = self_socket.new_close
            logging.debug("[socket] add %s:%d" %(client_ip, client_port))
            if client_list.get(client_ip, None) == None:
                client_list.update({client_ip : {"client_num":0, "last_up_time":0}})
            client_list[client_ip]["client_num"] += 1
            self._all_client_list[server_addrs].update(client_list)
            if set_close_timeout:
                self_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, recv_timeout)
            return return_value
        else:
            for k,v in self._all_client_list[server_addrs].copy().items():
                last_up_time = v["last_up_time"]
                if time.time() - last_up_time > recvfrom_timeout and v["client_num"] < 1:
                    if set_close_timeout:
                        self_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, recv_timeout)
                    logging.info("[socket] remove the client %s" % (k))
                    del client_list[k]
                    if client_list.get(client_ip, None) == None:
                        client_list.update({client_ip : {"client_num":0, "last_up_time":0}})
                    client_list[client_ip]["client_num"] += 1
                    self._all_client_list[server_addrs].update(client_list)
                    self_socket._server_addrs = self._server_addrs
                    self_socket.close = self_socket.new_close
                    return return_value
        if time.time() - self.last_log_time[0] > 10:
            logging.error("[socket] the server_addrs %s client more than the %d" % (server_addrs, limit_clients_num))
            self.last_log_time[0] = time.time()
        self_socket.close()


# 处理Udp连接
def new_recvfrom(orgin_method, self, *args, **kwds):

    while True:
        return_value = orgin_method(*args, **kwds)
        server_addrs = self._server_addrs
        client_ip, client_port = return_value[1]
        client_list = self._all_client_list.get(server_addrs, {})
        
        if len(client_list) < limit_clients_num or client_ip in client_list:
            if client_list.get(client_ip, None) == None:
                client_list.update({client_ip : {"client_num":0, "last_up_time":0}})
            client_list[client_ip]["last_up_time"] = time.time()
            self._all_client_list[server_addrs].update(client_list)
            logging.debug("[socket] update last_up_time for %s" % client_ip)
            return return_value
        else:
            for k,v in self._all_client_list[server_addrs].copy().items():
                last_up_time = v["last_up_time"]
                if time.time() - last_up_time > recvfrom_timeout and v["client_num"] < 1:
                    logging.info("[socket] remove the client %s" % (k))
                    del client_list[k]
                    logging.debug("[socket] add %s:%d" %(client_ip, client_port))
                    client_list.update({client_ip : {"client_num":0, "last_up_time":time.time()}})
                    self._all_client_list[server_addrs].update(client_list)
                    return return_value

        if time.time() - self.last_log_time[0] > 10:
            logging.error("[socket] the server_addrs %s client more than the %d" % (server_addrs, limit_clients_num))
            self.last_log_time[0] = time.time()
        new_tuple = [b'', return_value[1]]
        return_value = tuple(new_tuple)
        return return_value


def new_bind(orgin_method, self, *args, **kwds):
    
    # 如果绑定地址是0，那这个 socket 就一定不是和客户端通信的。
    # 此处主要是考虑到shadowsocks服务端在做流量转发的时候会对本地的socket进行绑定。
    if args[0][1] != 0:
        if only_port:
            server_addrs = '*:%s' % args[0][1]
        else:
            server_addrs = '%s:%s' % (args[0][0], args[0][1])
        self._server_addrs = server_addrs
        self._all_client_list.update({server_addrs:{}})
        new_self_method(self, 'recvfrom', new_recvfrom)
    orgin_method(self, *args, **kwds)
    


# 自定义 socket 类，可以自定义实例方法或属性。
class new_socket(socket.socket):

    def __init__(self, *args, **kwds):
        super(new_socket, self).__init__(*args, **kwds)


# 为 accept 生成的socket对象创建一个单独的类，目的是给其动态地绑定 close 方法。
class new_client_socket(socket.socket):

    def __init__(self, *args, **kwds):
        super(new_client_socket, self).__init__(*args, **kwds)

    def close(self ,*args, **kwds):
        super(new_client_socket, self).__init__(*args, **kwds)

    # 自定义 close 方法，让其在关闭的时候从列表中清理掉自身的 socket 或 ip。
    def new_close(self, *args, **kwds):
        addr, port = self.getpeername()
        server_addrs = self._server_addrs
        client_list = self._all_client_list[server_addrs]
        if client_list.get(addr, None) != None:
            last_up_time = client_list[addr]["last_up_time"]
            if client_list[addr]["client_num"] <= 1 and time.time() - last_up_time > recvfrom_timeout:
                del client_list[addr]
                logging.info("[socket] remove the client %s" % (addr))
            else:
                client_list[addr]["client_num"] -= 1
                logging.debug("[socket] close the client socket %s:%d" % (addr, port))
            self._all_client_list[server_addrs].update(client_list)
        return super(new_client_socket, self).close(*args, **kwds)


# 添加类属性， 此属性是全局的，所有socket对象都共享此属性。
setattr(socket.socket, '_all_client_list', {})
setattr(socket.socket, 'last_log_time', [0])

new_class_method(socket.socket, 'bind', new_bind)
new_class_method(socket.socket, 'accept', new_accept)
if not sys.version_info[0] >= 3:
    socket._socketobject = new_client_socket
socket.socket = new_socket