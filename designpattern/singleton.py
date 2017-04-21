# coding=utf-8
# when __new__ does need to create a new instance, it most often delegates creation by calling object.__new__ or the
# __new__ method of another superclass of C


# 方法1： 通过__new__方法来实现

class Singleton1(object):
    instance = None
    def __new__(cls, *args, **kwargs):
        if not cls.instance:
            cls.instance = super(Singleton1, cls).__new__(cls)
        return cls.instance


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




# 方法4：使用装饰器实现单例
def Singleton6(func):
    instances = {}
    def wrapper():
        if func not in instances:
            instances[func] = func()
        return func
    return wrapper

@Singleton6
def Foo():
    pass

@Singleton6
class MySingleton6(object):
    pass

f1 =Foo()
f2 =Foo()
c1 = MySingleton6()
c2 = MySingleton6()

print(f1 is f2)
print c1 is c2

#使用装饰器实现单例的另一个例子
def Singleton(cls):
    _instance = {}

    def _singleton(*args, **kargs):
        if cls not in _instance:
            _instance[cls] = cls(*args, **kargs)
        return _instance[cls]

    return _singleton


@Singleton
class A(object):
    a = 1
    def __init__(self, x=0):
        self.x = x


# 方法5：静态方法实现
class Singleton7:
    instance = None
    @staticmethod
    def get_instance():
        if not Singleton7.instance:
            Singleton7.instance = Singleton7()
        return Singleton7.instance
    def __new__(cls):
        pass

s1 = Singleton7.get_instance()
s2 = Singleton7.get_instance()
s3 = Singleton7()
s4 = Singleton7()
print s1 is s2  # True
print s3 is s4  # False
#总结：实现单例模式大体上有三种方法，第一种方法通过__new__方法来实现；第二种方法通过装饰器来实现；第三种方法通过静态方法来实现。
#其中第三种方法最容易理解,但是问题是必须要通过该静态方法来产生实例才可以


# __new__方法的实现方式 + 静态方法的实现方式
class Singleton8(object):
    instance = None
    @staticmethod
    def get_instance():
        if not Singleton8.instance:
            Singleton8.instance = Singleton8()
        return Singleton8.instance

    def __new__(cls,*args,**kwargs):
        if not cls.instance:
            cls.instance = super(Singleton8,cls).__new__(cls)
        return cls.instance
s1 = Singleton8()
s2 = Singleton8()
s3 = Singleton8.get_instance()
s4 = Singleton8.get_instance()

print s1 is s2
print s3 is s4