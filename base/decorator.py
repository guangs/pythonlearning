# encoding=utf-8
'''
装饰器是一个很著名的设计模式，经常被用于有切面需求的场景，较为经典的有插入日志、性能测试、事务处理等。
装饰器是解决这类问题的绝佳设计，有了装饰器，我们就可以抽离出大量函数中与函数功能本身无关的雷同代码并继续重用。
概括的讲，装饰器的作用就是为已经存在的对象添加额外的功能，同时并不改动已存在函数本身，也不改变原函数的调用方式。
下面就一步步看看Python中的装饰器。

装饰器模式本质: foo = deco(foo)
比如想看看执行某个函数用了多长时间，有以下几种方式：
1. 修改函数 foo2()  //缺点是原函数改变了，所有调用原函数的地方都要修改
2. 不修改原函数，用新的函数调用原函d缺点数timeit(foo)  //原函数本身没修改，但是所有原函数的调用都要用timeit(foo)
3. 装饰器模式，foo = timeit(foo) //原函数本身没修改，所有原函数的调用也没修改.
   只是增加新函数timeit和foo=timeit(foo), 这样完全符合“开闭原则”-对扩展开放，对修改封闭
import time

def foo():
    print 'in foo()'

# 定义一个计时器，传入一个，并返回另一个附加了计时功能的方法
def timeit(func):

    # 定义一个内嵌的包装函数，给传入的函数加上计时功能的包装
    def wrapper():
        start = time.clock()
        func()
        end =time.clock()
        print 'used:', end - start

    # 将包装后的函数返回
    return wrapper

foo = timeit(foo)
foo()

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
def deco4(name,**kwargs):
    def wrapper(func):
        print 'deco5 start ', name,kwargs
        print 'deco5 stop ', name,kwargs
        return func
    return wrapper

@deco4(name='demo_process',pid='100')
def myfunc4(a,b):
    print 'start myfunc ', a
    print 'stop myfunc ', b


myfunc4('hello','world')

'''第五种情况：装饰器本身带参数，被装饰的函数也带参数。下面的写法局限性在于装饰的部分职能在func之前执行，不能对func前后都装饰'''
def deco5(route):
    def wrapper(func):
        print 'before route{}'.format(route)
        print 'after route{}'.format(route)
        return func
    return wrapper

@deco5(route='/app/path')
def myfunc5(name):
    print 'hello {}'.format(name)

'''第六种情况：装饰器本身带参数，被装饰的函数也带参数'''
def deco6(route):
    def wrapper(func):
        def wrapper2(*args):
            print 'before route{}'.format(route)
            func(*args)
            print 'after route{}'.format(route)
        return wrapper2
    return wrapper

@deco6(route='/app/path')
def myfunc6(name):
    print 'hello {}'.format(name)

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

# practice
if __name__ == '__main__':
    pass


