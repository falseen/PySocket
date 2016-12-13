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
#          2.修改53、54行的 clean_time 和 ip_numbers 为你想要的数值。
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


clean_time = 60        # 设置清理ip的时间间隔，在此时间内无连接的ip会被清理
ip_numbers = 2         # 设置每个端口的允许通过的ip数量，即设置客户端ip数量
only_port = True       # 设置是否只根据端口判断。如果为 True ，则只根据端口判断。如果为 False ，则会严格的根据 服务端ip+端口进行判断

# 动态path类方法
def re_class_method(_class, method_name, re_method):
    method = getattr(_class, method_name)
    info = sys.version_info
    if info[0] >= 3:
        setattr(_class, method_name,
                types.MethodType(lambda *args, **kwds: re_method(method, *args, **kwds), _class))
    else:
        setattr(_class, method_name,
                types.MethodType(lambda *args, **kwds: re_method(method, *args, **kwds), None, _class))

# 动态path实例方法
def re_self_method(self, method_name, re_method):
    method = getattr(self, method_name)
    setattr(self, method_name, types.MethodType(lambda *args, **kwds: re_method(method, *args, **kwds), self, self))


# 处理Tcp连接
def re_accept(old_method, self, *args, **kwds):

    while True:

        return_value = old_method(self, *args, **kwds)
        self_socket = return_value[0]
        
        if only_port:
            server_ip_port = '%s' % self.getsockname()[1]
        else:
            server_ip_port = '%s_%s' % (self.getsockname()[0], self.getsockname()[1])

        client_ip = return_value[1][0]

        client_ip_list = [x[0].split('#')[0] for x in self._list_client_ip[server_ip_port]]
        
        if len(self._list_client_ip[server_ip_port]) == 0:
            logging.debug("[re_socket] first add %s" % client_ip)
            self._list_client_ip[server_ip_port].append(['%s#%s' % (client_ip, time.time()), self_socket])
            return return_value

        if client_ip in client_ip_list:
            logging.debug("[re_socket] update socket in %s" % client_ip)
            _ip_index = client_ip_list.index(client_ip)
            self._list_client_ip[server_ip_port][_ip_index][0] = '%s#%s' % (client_ip, time.time())
            self._list_client_ip[server_ip_port][_ip_index].append(self_socket)
            return return_value

        else:
            if len(self._list_client_ip[server_ip_port]) < ip_numbers:
                logging.debug("[re_socket] add %s" % client_ip)
                self._list_client_ip[server_ip_port].append(['%s#%s' % (client_ip, time.time()), self_socket])
                return return_value

            for x in [x for x in self._list_client_ip[server_ip_port]]:
                is_closed = True
                if time.time() - float(x[0].split('#')[1]) > clean_time:

                    for y in x[1:]:
                        try:
                            y.getpeername()     # 判断连接是否关闭
                            is_closed = False
                            break
                        except:                # 如果抛出异常，则说明连接已经关闭，这时可以关闭套接字
                            logging.debug("[re_socket] close and remove the time out socket 1/%s" % (len(x[1:])))
                            x.remove(y)

                    if not is_closed:
                        logging.debug('[re_socket] the %s still exists and update last_time' % str(x[1].getpeername()[0]))
                        _ip_index = client_ip_list.index(x[0].split('#')[0])
                        self._list_client_ip[server_ip_port][_ip_index][0] = '%s#%s' % (x[0].split('#')[0], time.time())

                    else:
                        logging.info("[re_socket] remove time out ip and add new ip %s" % client_ip )
                        self._list_client_ip[server_ip_port].remove(x)
                        self._list_client_ip[server_ip_port].append(['%s#%s' % (client_ip, time.time()), self_socket])
                        return return_value

        if int(time.time()) % 5 == 0:
            logging.debug("[re_socket] the port %s client more then the %s" % (server_ip_port, ip_numbers))

# 处理Udp连接
def re_recvfrom(old_method, self, *args, **kwds):

    while True:
        return_value = old_method(*args, **kwds)
        self_socket = ''
        if only_port:
            server_ip_port = '%s' % self.getsockname()[1]
        else:
            server_ip_port = '%s_%s' % (self.getsockname()[0], self.getsockname()[1])
        client_ip = return_value[1][0]
        client_ip_list = [x[0].split('#')[0] for x in self._list_client_ip[server_ip_port]]

        if len(self._list_client_ip[server_ip_port]) == 0:
            logging.debug("[re_socket] first add %s" % client_ip)
            self._list_client_ip[server_ip_port].append(['%s#%s' % (client_ip, time.time()), self_socket])
            return return_value

        if client_ip in client_ip_list:
            logging.debug("[re_socket] update socket in %s" % client_ip)
            _ip_index = client_ip_list.index(client_ip)
            self._list_client_ip[server_ip_port][_ip_index][0] = '%s#%s' % (client_ip, time.time())
            return return_value
        else:
            if len(self._list_client_ip[server_ip_port]) < ip_numbers:
                logging.debug("[re_socket] add %s" % client_ip)
                self._list_client_ip[server_ip_port].append(['%s#%s' % (client_ip, time.time()), self_socket])
                return return_value

            for x in [x for x in self._list_client_ip[server_ip_port]]:
                is_closed = True
                if time.time() - float(x[0].split('#')[1]) > clean_time:

                    for y in x[1:]:
                        try:
                            y.getpeername()     # 判断连接是否关闭
                            is_closed = False
                            break
                        except:                # 如果抛出异常，则说明连接已经关闭，这时可以关闭套接字
                            logging.debug("[re_socket] close and remove the time out socket 1/%s" % (len(x[1:])))
                            x.remove(y)

                    if not is_closed:
                        logging.debug('[re_socket] the %s still exists and update last_time' % str(x[1].getpeername()[0]))
                        _ip_index = client_ip_list.index(x[0].split('#')[0])
                        self._list_client_ip[server_ip_port][_ip_index][0] = '%s#%s' % (x[0].split('#')[0], time.time())

                    else:
                        logging.info("[re_socket] remove time out ip and add new ip %s" % client_ip )
                        self._list_client_ip[server_ip_port].remove(x)
                        self._list_client_ip[server_ip_port].append(['%s#%s' % (client_ip, time.time()), self_socket])
                        return return_value

        if int(time.time()) % 5 == 0:
            logging.debug("[re_socket] the port %s client more then the %s" % (server_ip_port, ip_numbers))
        new_tuple = [b'', return_value[1]]
        return_value = tuple(new_tuple)
        return return_value


def re_bind(old_method, self, *args, **kwds):
    if only_port:
        port = '%s' % args[0][1]
    else:
        port = '%s_%s' % (args[0][0], args[0][1])
    self._list_client_ip[port] = []
    re_self_method(self, 'recvfrom', re_recvfrom)
    old_method(self, *args, **kwds)


setattr(socket.socket, '_list_client_ip', {})
re_class_method(socket.socket, 'bind', re_bind)
re_class_method(socket.socket, 'accept', re_accept)

