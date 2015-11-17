#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# 功能：限制客户端数量（基于ip判断）
#
# 使用说明：将此文件放在ss根目录中即可生效，不用做其他设置（需要重新运行ss）。
# 修改36行的 clean_time 和 ip_numbers 为你想要的数值。
#
# 原理：默认情况下，ss在运行的时候会引用系统中的socket文件，但是把这个socket文件放到ss目录之后,ss就会引用这个我们自定义的socket文件。
#      然后在这个文件中再引用真正的socket包，并在原socket的基础上加以修改，最终ss调用的就是经过我们修改的socket文件了。
#
# 所以理论上任何引用了socket包的python程序都可以用这个文件来达到限制连接的ip数量的目的。
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


clean_time = 60         # 设置清理ip的时间间隔，在此时间内无连接的ip会被清理
ip_numbers = 1         # 设置每个端口的允许通过的ip数量，即设置客户端ip数量


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
        return [x.split('-')[0] for x in self._list_client_ip]

    def server_ip_port_client_ip_list():
        return [x.split('#')[0] for x in self._list_client_ip]

    def last_time(server_ip_port_client_ip):
        for x in self._list_client_ip:
            if server_ip_port_client_ip in x:
                return float(x.split('#')[1])

    while True:

        return_value = old_method(self, *args, **kwds)  # call the original method
        server_ip_port = '%s_%s' % (self.getsockname()[0], self.getsockname()[1])
        server_ip_port_client_ip = server_ip_port + '-' + return_value[1][0]

        if len(self._list_client_ip) == 0:
            logging.debug("[socket] first add %s" % server_ip_port_client_ip)
            self._list_client_ip.append('%s#%s' % (server_ip_port_client_ip, time.time()))
            return return_value

        if server_ip_port_list().count(server_ip_port) < ip_numbers:
            if server_ip_port_client_ip in server_ip_port_client_ip_list() \
                    and time.time() - last_time(server_ip_port_client_ip) > 30:   # 如果存在,并且距上次更新相差30秒，则更新时间
                _ip_index = server_ip_port_client_ip_list().index(server_ip_port_client_ip)
                self._list_client_ip[_ip_index] = '%s#%s' % (server_ip_port_client_ip, time.time())
                logging.debug('[socket] update the ip time')
            elif server_ip_port_client_ip not in server_ip_port_client_ip_list() :
                self._list_client_ip.append('%s#%s' % (server_ip_port_client_ip, time.time()))
                logging.debug("[socket] add %s" % server_ip_port_client_ip)
            return return_value

        if server_ip_port_client_ip not in server_ip_port_client_ip_list():
            for x in [x for x in self._list_client_ip if x.split('-')[0] == server_ip_port]:
                if time.time() - float(x.split('#')[1]) - 30 > clean_time:
                    self._list_client_ip.remove(x)
                    self._list_client_ip.append('%s#%s' % (server_ip_port_client_ip, time.time()))
                    logging.info("[socket] remove time out ip and add new ip %s" % server_ip_port_client_ip )
                    return return_value
            logging.debug("[socket] client more then the %s" % ip_numbers)
        else:
            return return_value


enhance_method(socket.socket, 'accept', re_accept)
setattr(socket.socket, '_list_client_ip', [])


