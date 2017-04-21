#!/usr/bin/python
# -*- coding: utf-8 -*-
# Description: test the threading.local class
# 

from threading import local, enumerate, Thread, currentThread

local_data = local()
local_data.name = 'local_data'

class TestThread(Thread):
        def run(self):
                print currentThread()
                print local_data.__dict__
                local_data.name = self.getName()
                local_data.add_by_sub_thread = self.getName()
                print local_data.__dict__

if __name__ == '__main__':
        print currentThread()
        print local_data.__dict__
        
        t1 = TestThread()
        t1.start()
        t1.join()
        
        t2 = TestThread()
        t2.start()
        t2.join()
        
        print currentThread()
        print local_data.__dict__

'''
主线程中的local_data并没有被改变，而子线程中的local_data各自都不相同。

怎么这么神奇？local_data具有全局访问权，主线程，子线程都能访问它，但是它的值却是各当前线程有关，究竟什么奥秘在这里呢？

查看了一下local的源代码，发现就神奇在_path()方法中:

def _patch(self):
    key = object.__getattribute__(self, '_local__key')
    d = currentThread().__dict__.get(key)
    if d is None:
        d = {}
        currentThread().__dict__[key] = d
        object.__setattr__(self, '__dict__', d)

        # we have a new instance dict, so call out __init__ if we have
        # one
        cls = type(self)
        if cls.__init__ is not object.__init__:
            args, kw = object.__getattribute__(self, '_local__args')
            cls.__init__(self, *args, **kw)
    else:
        object.__setattr__(self, '__dict__', d)

 

每次调用local实例的属性前，local都会调用这个方法，找到它保存值的地方.

d = currentThread().__dict__.get(key)  就是这个地方，确定了local_data值的保存位置。所以子线程访问local_data时，并不是获取主线程的local_data的值，在子线程第一次访问它是，它是一个空白的字典对象，所以local_data.__dict__为 {}，就像我们的输出结果一样。

如果想在当前线程保存一个全局值，并且各自线程互不干扰，使用local类吧。
'''