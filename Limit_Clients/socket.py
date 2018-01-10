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
#          2.修改 recv_timeout 和 Limit_Clients_Num 为你想要的数值。
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
import struct

path = sys.path[0]
sys.path.pop(0)

# import real socket
import socket    

sys.path.insert(0, path)


#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

set_close_timeout = True    # 是否清理指定时间内无数据收发的连接，仅对TCP有效，socket会自动关闭正常或异常断开的连接, 所以一般不用设置。
                            #   如果为True则根据下面的 recv_timeout 进行清理，如果为 False 则根据socket的默认超时时间来清理(5分钟左右)。

recv_timeout = 120          # 配合上面的选项设置 tcp 清理连接的超时时间，单位秒。在此时间内无连接或无数据 收发 的连接会被清理。
                            #    只针对 tcp。一般客户端在关闭的时候会主动关闭连接，此选项主要是应对客户端的非正常关闭。
                            #    比如说突然断网之类的。建议不要设置为0或120以下，因为 tcp keepalive 的默认时间一般是120秒。

recvfrom_timeout = 30       # 设置 udp 清理连接的超时时间，单位秒。在此时间内无连接或无数据 接收 的连接会被清理。只针对 udp。

Limit_Clients_Num = 1       # 设置每个端口的默认允许通过的ip数量，即客户端的ip数量。
                            #   此为默认值，如果黑名单中没有定义，则按此选项的值来设置。

only_port = True            # 设置是否只根据端口判断。如果为 True ，则只根据端口判断。如果为 False ，则会严格的根据服务端ip+端口进行判断。
                            #     此功能主要适用于服务端有多个ip的情况，比如同时拥有ipv4和ipv6的ip。

# 白名单，在此名单内的端口不受限制，可以留空。格式 white_list = [80, 443] 端口间用半角逗号分隔，注意一定要是数字，不能加引号。
white_list = []

# 黑名单，在此名单内的端口会受到限制, 可以留空。
# 格式 端口:ip数量， black_list = {80:1, 443:2} 如果白名单和黑名单都留空，则默认限制所有端口。
black_list = {}

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

PYTHON_VERSION = sys.version_info[0]
send_timeout = recv_timeout
limit_all_clients = False

if not black_list and not white_list:
    limit_all_clients = True

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
        return_value = orgin_method(*args, **kwds)
        self_socket = return_value[0]
        client_ip, client_port = return_value[1][:2]
        server_addrs = self._server_addrs
        client_list = self._all_client_list.get(server_addrs, {})
        if len(client_list) < self._limit_clients_num or client_ip in client_list:
            self_socket._server_addrs = self._server_addrs
            self_socket.close = self_socket.new_close
            logging.debug("[socket] add client %s:%d" %(client_ip, client_port))
            if client_list.get(client_ip, None) == None:
                client_list.update({client_ip : {"client_num":0, "last_up_time":0}})
            client_list[client_ip]["client_num"] += 1
            self._all_client_list[server_addrs].update(client_list)
            if set_close_timeout:
                # set recv_timeout and send_timeout , struct.pack("II", some_num_secs, some_num_microsecs)
                self_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, struct.pack("LL", recv_timeout, 0))
                self_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, struct.pack("LL", send_timeout, 0))
            return return_value
        else:
            for k,v in self._all_client_list[server_addrs].copy().items():
                last_up_time = v["last_up_time"]
                if time.time() - last_up_time > recvfrom_timeout and v["client_num"] < 1:
                    if set_close_timeout:
                        self_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, struct.pack("LL", recv_timeout, 0))
                        self_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, struct.pack("LL", send_timeout, 0))
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
            logging.error("[socket] the server_addrs %s client more than %d" % (server_addrs, self._limit_clients_num))
            self.last_log_time[0] = time.time()
        self_socket.close()


# 处理Udp连接
def new_recvfrom(orgin_method, self, *args, **kwds):
    return_value = orgin_method(*args, **kwds)
    server_addrs = self._server_addrs
    client_ip, client_port = return_value[1][:2]
    client_list = self._all_client_list.get(server_addrs, {})
    
    if len(client_list) < self._limit_clients_num or client_ip in client_list:
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
                logging.debug("[socket] add client %s:%d" %(client_ip, client_port))
                client_list.update({client_ip : {"client_num":0, "last_up_time":time.time()}})
                self._all_client_list[server_addrs].update(client_list)
                return return_value

    if time.time() - self.last_log_time[0] > 10:
        logging.error("[socket] the server_addrs %s client more than %d" % (server_addrs, self._limit_clients_num))
        self.last_log_time[0] = time.time()
    new_tuple = [b'', return_value[1]]
    return_value = tuple(new_tuple)
    return return_value


def new_bind(orgin_method, self, *args, **kwds):
    
    server_addres, server_port = args[0][:2]
    # 如果绑定地址是0，那这个 socket 就一定不是和客户端通信的。
    # 此处主要是考虑到shadowsocks服务端在做流量转发的时候会对本地的socket进行绑定。
    if args[0][1] != 0:
        if server_port in black_list or server_port not in white_list or limit_all_clients:
            if only_port:
                server_addrs = '*:%s' % server_port
            else:
                server_addrs = '%s:%s' % (server_addres, server_port)
            self._server_addrs = server_addrs
            self._all_client_list.update({server_addrs:{}})
            self._limit_clients_num = black_list.get(server_port, Limit_Clients_Num)
            logging.debug("[socket] bind the new new_accept new_recvfrom")
            new_self_method(self, 'accept', new_accept)
            if self.type == socket.SOCK_DGRAM:
                new_self_method(self, 'recvfrom', new_recvfrom)
    if PYTHON_VERSION >= 3:
        orgin_method(*args, **kwds)
    else:
        orgin_method(self, *args, **kwds)
    


# 自定义 socket 类，可以自定义实例方法或属性。
# 为 accept 生成的socket对象创建一个单独的类，目的是给其动态地绑定 close 方法。
class new_socket(socket.socket):

    def __init__(self, *args, **kwds):
        super(new_socket, self).__init__(*args, **kwds)
        if PYTHON_VERSION >= 3:
            new_class_method(self, 'bind', new_bind)

    def close(self ,*args, **kwds):
        super(new_socket, self).__init__(*args, **kwds)
        
    # 自定义 close 方法，让其在关闭的时候从列表中清理掉自身的 socket 或 ip。
    def new_close(self, *args, **kwds):
        addr, port = self.getpeername()[0:2]
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
        return super(new_socket, self).close(*args, **kwds)
            


# 添加类属性， 此属性是全局的，所有socket对象都共享此属性。
setattr(socket.socket, '_all_client_list', {})
setattr(socket.socket, 'last_log_time', [0])

# python2
if not PYTHON_VERSION >= 3:
    new_class_method(socket.socket, 'bind', new_bind)
    socket._socketobject = new_socket
socket.socket = new_socket
