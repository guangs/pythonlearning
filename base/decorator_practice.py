# encoding=utf-8

def deco(route):
    def wrapper(func):
        print 'before route{}'.format(route)
        print 'after route{}'.format(route)
        return func
    return wrapper


def deco2(route):
    def wrapper(func):
        def wrapper2(*args):
            print 'before route{}'.format(route)
            func(*args)
            print 'after route{}'.format(route)
        return wrapper2
    return wrapper


def deco3(func):
    def wrapper(*args):
        print 'before'
        func(*args)
        print 'after'
    return wrapper


def deco4(func):
    print 'before'
    print 'after'
    return func

# @deco(route='/app/path')
# @deco2(route='/app/path')
# @deco3
# @deco4
# def foo(name):
#     print 'hello {}'.format(name)

# @deco(route='/app/path')
# @deco2(route='/app/path')
# @deco3

''' deco 和deco4这种通过return func的方式，需要注意的是，在多次@deco的时候，即使调用一次也会出现多次。
下面是foo3执行后的结果，可见before,after执行了两次，因为@deco(route='/app/path')两次
before route/app/path
after route/app/path
before route/app/path
after route/app/path
hello world
'''

@deco(route='/app/path')
def foo2():
    print 'hello world'

@deco(route='/app/path')
def foo3():
    print 'hello world'

# foo('Michael')

foo3()