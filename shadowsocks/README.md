# PySocket


## 功能：

注意：这是python代码，因此只支持python版的shadowsocks。

给服务端添加前置代理（原则上也适用于客户端），支持 http、socks4、socks5 代理。并且通过hook的方式去掉了ss的dns查询，ss在接收到数据之后会直接把域名和请求一起发给代理。

**使用的时候修改 socket.py 文件中 PROXY_TYPE、PROXY_ADDR、PROXY_PORT 等字段为你的代理地址，然后放到 shadowsocks 根目录即可生效。不用修改任何源码。**

如果不想 hook shadowsocks的代码的话，把文件中末尾的代码删除即可，如下:

```python
# hook shadowsocks's code remove the dns req
def new_resolve(self,  hostname, callback):
    callback((hostname, hostname), None)

modules_list = ["shadowsocks.common", "shadowsocks.shell"]
for x in modules_list:
    del sys.modules[x]

import shadowsocks.asyncdns
shadowsocks.asyncdns.DNSResolver.resolve = new_resolve

```


* **dns_forward 文件夹** : 简单的端口转发，可以把服务端访问（从客户端接收到的请求）某个ip的流量强制转到另外一个ip。比如当手机端开启udp转发的时候，可以把手机端访问 8.8.8.8:53的流量转移到 114.114.114.114:53，或是内网的dns。这个功能主要是为那些服务端搭建在国内、把ss当vpn使用的人准备的。

## TODO
增加类似acl的功能，过滤一些本地私有地址或其他地址。
