#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2015 Falseen
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
# 使用说明：1.将此文件放在ss根目录中即可生效，不用做其他设置（需要重新运行ss）。
#          2.修改53、54行的 recv_timeout 和 client_num 为你想要的数值。
#          3.如果你的服务器有ipv6,并且你想让ip4和ip6分开限制，则可以设置 only_port 为 False 。
#
#
# 原理：默认情况下，ss在运行的时候会引用系统中的socket文件，但是把这个socket文件放到ss目录之后,ss就会引用这个我们自定义的socket文件。
#      然后在这个文件中再引用真正的socket包，并在原socket的基础上加以修改，最终ss调用的就是经过我们修改的socket文件了。
#
# 所以理论上任何引用了socket包的python程序都可以用这个文件来达到限制连接ip数量的目的。
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



set_close_timeout = True  # 是否清理指定时间内无数据收发的连接， 如果为True则根据下面的两个选项进行清理，否则如果为 False 则不清理。
recv_timeout = 10         # 设置清理连接的超时时间，在此时间内无连接或无数据 接收 的连接会被清理。
send_timeout = 10       # 设置清理连接的超时时间，在此时间内无连接或无数据 发送 的连接会被清理。
client_num = 1            # 设置每个端口的允许通过的ip数量，即设置客户端ip数量
only_port = True          # 设置是否只根据端口判断。如果为 True ，则只根据端口判断。如果为 False ，则会严格的根据 服务端ip+端口进行判断


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
    setattr(self, method_name, types.MethodType(lambda *args, **kwds: new_method(method, *args, **kwds), self, self))


# 处理Tcp连接
def new_accept(orgin_method, self, *args, **kwds):

    def new_close(orgin_method, socket_self, *args, **kwds):
        addr, port = socket_self.getpeername()
        if self._client_list[addr] <= 1:
            del self._client_list[addr]
            logging.info("[socket] remove the client %s" % (addr))
        else:
            self._client_list[addr] -= 1
            logging.info("[socket] close the client socket %s:%d" % (addr, port))
        return orgin_method(*args, **kwds)

    while True:
        return_value = orgin_method(self, *args, **kwds)
        self_socket = return_value[0]
        client_ip, client_port = return_value[1]
        if len(self._client_list) < client_num or client_ip in self._client_list:
            new_self_method(return_value[0], 'close', new_close)
            logging.info("[socket] add %s:%d" %(client_ip, client_port))
            if self._client_list.get(client_ip, None) == None:
                self._client_list.update({client_ip : 0})
            self._client_list[client_ip] += 1
            if set_close_timeout:
                self_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, recv_timeout)
                self_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, send_timeout)
                self_socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, 0)
            return return_value
        server_addr, server_port = self.getsockname()
        logging.info("[socket] the %s:%d client more then the %s" % (server_addr, server_port, client_num))
        self_socket.close()     

# 处理Udp连接
def new_recvfrom(orgin_method, self, *args, **kwds):

    while True:
        return_value = orgin_method(*args, **kwds)
        self_socket = ''
        if only_port:
            server_ip_port = '%s' % self.getsockname()[1]
        else:
            server_ip_port = '%s_%s' % (self.getsockname()[0], self.getsockname()[1])
        client_ip = return_value[1][0]
        client_ip_list = [x[0].split('#')[0] for x in self._list_client_ip[server_ip_port]]

        if len(self._list_client_ip[server_ip_port]) == 0:
            logging.debug("[socket] first add %s" % client_ip)
            self._list_client_ip[server_ip_port].append(['%s#%s' % (client_ip, time.time()), self_socket])
            return return_value

        if client_ip in client_ip_list:
            logging.debug("[socket] update socket in %s" % client_ip)
            _ip_index = client_ip_list.index(client_ip)
            self._list_client_ip[server_ip_port][_ip_index][0] = '%s#%s' % (client_ip, time.time())
            return return_value
        else:
            if len(self._list_client_ip[server_ip_port]) < client_num:
                logging.debug("[socket] add %s" % client_ip)
                self._list_client_ip[server_ip_port].append(['%s#%s' % (client_ip, time.time()), self_socket])
                return return_value

            for x in [x for x in self._list_client_ip[server_ip_port]]:
                is_closed = True
                if time.time() - float(x[0].split('#')[1]) > recv_timeout:

                    for y in x[1:]:
                        try:
                            y.getpeername()     # 判断连接是否关闭
                            is_closed = False
                            break
                        except:                # 如果抛出异常，则说明连接已经关闭，这时可以关闭套接字
                            logging.debug("[socket] close and remove the time out socket 1/%s" % (len(x[1:])))
                            x.remove(y)

                    if not is_closed:
                        logging.debug('[socket] the %s still exists and update last_time' % str(x[1].getpeername()[0]))
                        _ip_index = client_ip_list.index(x[0].split('#')[0])
                        self._list_client_ip[server_ip_port][_ip_index][0] = '%s#%s' % (x[0].split('#')[0], time.time())

                    else:
                        logging.info("[socket] remove time out ip and add new ip %s" % client_ip )
                        self._list_client_ip[server_ip_port].remove(x)
                        self._list_client_ip[server_ip_port].append(['%s#%s' % (client_ip, time.time()), self_socket])
                        return return_value

        if int(time.time()) % 5 == 0:
            logging.debug("[socket] the port %s client more then the %s" % (server_ip_port, client_num))
        new_tuple = [b'', return_value[1]]
        return_value = tuple(new_tuple)
        return return_value


def new_bind(orgin_method, self, *args, **kwds):
    #new_self_method(self, 'recvfrom', new_recvfrom)
    orgin_method(self, *args, **kwds)


class new_socket(socket.socket):

    def __init__(self, *args, **kwds):
        super(new_socket, self).__init__(*args, **kwds)
        # new_self_method(self, 'sendto', new_sendto)
        # new_self_method(self, 'recvfrom', new_recvfrom)
        self._client_list = {}

    def close(self, *args, **kwds):
        super(new_socket, self).__init__(*args, **kwds)


class new_client_socket(socket.socket):

    def __init__(self, *args, **kwds):
        super(new_client_socket, self).__init__(*args, **kwds)

    def close(self ,*args, **kwds):
        super(new_client_socket, self).__init__(*args, **kwds)

new_class_method(socket.socket, 'bind', new_bind)
new_class_method(socket.socket, 'accept', new_accept)
socket.socket = new_socket
socket._socketobject = new_client_socket