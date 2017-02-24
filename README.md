# PySocket

## 功能

通过猴子补丁的方式给 socket 动态地添加一些增强功能，比如限制客户端数量、前置代理什么的。
**使用的时候只要把对应文件夹中的 socket.py 文件放到程序的目录即可生效，不用修改任何源码。**

## 说明：

项目中每个文件夹代表不同的功能。
以下是每个文件夹的功能和说明。

* **shadowosocks**： 给服务端添加前置代理（原则上也适用于客户端），支持 http、socks4、socks5 代理。并且通过hook的方式去掉了ss的dns查询，ss在接收到数据之后会直接把域名和请求一起发给代理。
      
* **proxy**：基本跟shadowoscks一样，只是去掉了hook的代码。

* **Limit_Clients**：限制客户端数量（基于ip），这是以前的代码，很久没更新了。随后可能会更新。

* **orgin_socket**：原始的socket，放在这里只是为了方便查看代码。毕竟 _socket.pyd 是加密的。


部分代码来自 PySocks 项目：https://github.com/Anorov/PySocks


## 原理说明：

默认情况下，python程序在运行的时候会导入系统中的 socket 文件，但是把这个socket文件放到程序的目录之后, 它就会引用这个我们自定义的socket文件。 然后我们再在这个文件中再导入真正的socket包，并在原 socket 的基础上加以修改，最终程序调用的就是经过我们修改的socket文件了。

最后我想说的是，python 真的是世界上最好的语言，太自由了！！！