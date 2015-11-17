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
only_port = True       # 设置是否只根据端口判断。如果为 True ，则只根据端口判断。如果为 False ，则会严格的根据 ip+端口进行判断。


def enhance_method(_class, method_name, replacement):
    method = getattr(_class, method_name)
    info = sys.version_info
    if info[0] == 3:
        setattr(_class, method_name,
                types.MethodType(lambda *args, **kwds: replacement(method, *args, **kwds), _class))
    else:
        setattr(_class, method_name,
                types.MethodType(lambda *args, **kwds: replacement(method, *args, **kwds), None, _class))


def re_accept(old_method, self, *args, **kwds):

    def server_ip_port_list():
        return [x[0].split('-')[0] for x in self._list_client_ip]

    def server_ip_port_client_ip_list():
        return [x[0].split('#')[0] for x in self._list_client_ip]

    while True:

        return_value = old_method(self, *args, **kwds)  # call the original method
        self_socket = return_value[0]
        if only_port:
            server_ip_port = '%s' % self.getsockname()[1]
        else:
            server_ip_port = '%s_%s' % (self.getsockname()[0], self.getsockname()[1])

        server_ip_port_client_ip = '%s-%s' % (server_ip_port, return_value[1][0])
        if len(self._list_client_ip) == 0:
            logging.debug("[re_socket] first add %s" % server_ip_port_client_ip)
            self._list_client_ip.append(['%s#%s' % (server_ip_port_client_ip, time.time()), self_socket])
            return return_value

        if server_ip_port_client_ip in server_ip_port_client_ip_list():
            logging.debug("[re_socket] update socket in %s" % server_ip_port_client_ip)
            _ip_index = server_ip_port_client_ip_list().index(server_ip_port_client_ip)
            self._list_client_ip[_ip_index][0] = '%s#%s' % (server_ip_port_client_ip, time.time())
            self._list_client_ip[_ip_index].append(self_socket)
            return return_value

        else:
            if server_ip_port_list().count(server_ip_port) < ip_numbers:
                logging.debug("[re_socket] add %s" % server_ip_port_client_ip)
                self._list_client_ip.append(['%s#%s' % (server_ip_port_client_ip, time.time()), self_socket])
                return return_value

            for x in [x for x in self._list_client_ip if x[0].split('-')[0] == server_ip_port]:
                is_closed = True
                if time.time() - float(x[0].split('#')[1]) > clean_time:

                    for y in x[1:]:
                        try:
                            y.getpeername()     # 判断连接是否关闭
                            is_closed = False
                            break
                        except:                # 如果抛出异常，则说明连接已经关闭，这时可以关闭套接字
                            logging.debug("[re_socket] close and remove the time out socket 1/%s" % (len(x[1:])))
                            y.close()
                            x.remove(y)

                    if not is_closed:
                        logging.debug('[re_socket] the %s still exists and update last_time' % str(x[1].getpeername()[0]))
                        _ip_index = server_ip_port_client_ip_list().index(x[0].split('#')[0])
                        self._list_client_ip[_ip_index][0] = '%s#%s' % (x[0].split('#')[0], time.time())

                    else:
                        logging.info("[re_socket] remove time out ip and add new ip %s" % server_ip_port_client_ip )
                        self._list_client_ip.remove(x)
                        self._list_client_ip.append(['%s#%s' % (server_ip_port_client_ip, time.time()), self_socket])
                        return return_value

        if int(time.time()) % 10 == 0:
            logging.debug("[re_socket] the port %s client more then the %s" % (server_ip_port, ip_numbers))


enhance_method(socket.socket, 'accept', re_accept)
setattr(socket.socket, '_list_client_ip', [])


