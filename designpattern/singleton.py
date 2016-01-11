# coding=utf-8
# when __new__ does need to create a new instance, it most often delegates creation by calling object.__new__ or the
# __new__ method of another superclass of C


# 方法1： 通过__new__方法来实现

class Singleton1(object):
    _instance = {}

    def __new__(cls, *args, **kwargs):
        if cls not in cls._instance:
            cls._instance[cls] = super(Singleton1, cls).__new__(cls)
        return cls._instance[cls]


class Singleton2(object):
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(Singleton2,cls).__new__(cls)
        return cls._instance


class Singleton3(object):
    def __new__(cls, *args, **kwargs):
        if '_instance' not in dir(cls):
            cls._instance = super(Singleton3,cls).__new__(cls)
        return cls._instance


class Singleton4(object):
    def __new__(cls, *args, **kwargs):
        if '_instance' not in cls.__dict__:
            cls._instance = super(Singleton4,cls).__new__(cls)
        return cls._instance


# 方法2： 共享属性;所谓单例就是所有引用(实例、对象)拥有相同的状态(属性)和行为(方法)
# 同一个类的所有实例天然拥有相同的行为(方法),
# 只需要保证同一个类的所有实例具有相同的状态(属性)即可
# 所有实例共享属性的最简单最直接的方法就是__dict__属性指向(引用)同一个字典(dict)
# 可参看:http://code.activestate.com/recipes/66531/
# http://blog.csdn.net/ghostfromheaven/article/details/7671853

class Singleton5(object):
    _dict = {}

    def __new__(cls, *args, **kwargs):
        obj = super(Singleton5,cls).__new__(cls)
        obj.__dict__ = cls._dict
        return obj
# 注意这种方法创建的对象并不是同一个引用，但是对象的属性和方法指向同一个引用，这点和__new__方法创建的单例是不一样的。

# 方法3: 使用__metaclass__(元类)，本质上是方法1的高级版




# 方法4：使用装饰器，也是方法1的高级版

s1 = Singleton5()
s2 = Singleton5()

print id(s1)
print id(s2)