# encoding=utf-8
'''
Python装饰器,装饰模式有很多经典的使用场景，例如插入日志、性能测试、事务处理等等，有了装饰器，就可以提取大量函数中与本身功能无关的类似代码，从而达到代码重用的目的。
下面就一步步看看Python中的装饰器。
'''


'''第一种情况：被装饰的函数无参数'''
def deco1(func):
    def wrapper():
        print 'deco1 start'
        func()
        print 'deco1 stop'
    return wrapper

@deco1
def myfunc():
    print 'start myfunc'
    # time.sleep(1)
    print 'end myfunc'


'''第二种情况：被装饰的函数有参数'''
def deco2(func):
    def wrapper(a,b):
        print 'deco2 start'
        func(a,b)
        print 'deco2 stop'
    return wrapper

@deco2
def myfunc2(a,b):
    print 'start myfunc'
    print a,b
    print 'stop myfunc'


'''第三种情况：装饰器本身带参数'''
def deco3(arg=True):
    if arg:
        def _deco(func):
            def wrapper(a,b):
                print 'deco3 start'
                func(a,b)
                print 'deco3 stop'
            return wrapper
    else:
        def _deco(func):
            return func
    return _deco


@deco3(True)
def myfunc3(a,b):
    print 'start myfunc'
    print a,b
    print 'stop myfunc'


'''第四种情况：下面的这种写法很不一样，比较通用，但是局限性在于装饰的部分职能在func之前执行，不能对func前后都装饰'''
def deco5(name,**kwargs):
    def wrapper(func):
        print 'deco5 start ', name,kwargs
        print 'deco5 stop ', name,kwargs
        return func
    return wrapper

@deco5(name='demo_process',pid='100')
def myfunc5(a,b):
    print 'start myfunc ', a
    print 'stop myfunc ', b


myfunc5('hello','world')


'''
装饰器调用顺序
装饰器是可以叠加使用的，那么这是就涉及到装饰器调用顺序了。对于Python中的"@"语法糖，装饰器的调用顺序与使用 @ 语法糖声明的顺序相反。'''

@deco2
@deco3(True)
def myfunc4(a,b):
    print 'start myfunc'
    print a,b
    print 'stop myfunc'

# myfunc4('google','baidu')


'''
在Python中有三个内置的装饰器，都是跟class相关的：staticmethod,classmethod 和property
对于staticmethod和classmethod这里就不介绍了，通过一个例子看看property.
'''

class Student(object):

    def __init__(self,name):
        self._name = name

    @property
    def name(self): # 注意这个方法的名字name不能与属性的名字相同。这里方法的名字是name，属性的名字是_name
        return self._name

# s = Student('Li Ming')
# print s.name



