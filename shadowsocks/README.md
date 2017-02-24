# PySocket


## 功能：
通过猴子补丁的方式给 socket 动态地添加一些增强功能，比如限制客户端数量、前置代理什么的。
**使用的时候只要把对应文件夹中的 socket.py 文件放到程序的目录即可生效，不用修改任何源码。**

* **shadowosocks**： 给服务端添加前置代理（原则上也适用于客户端），支持 http、socks4、socks5 代理。并且通过hook的方式去掉了ss的dns查询，ss在接收到数据之后会直接把域名和请求一起发给代理。

使用的时候修改 socket.py 文件中 PRROXY_TYPE、PROXY_ADDR、PROXY_PORT 等字段为你的代理地址，然后放到 shadowsocks 根目录即可生效。
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
      

