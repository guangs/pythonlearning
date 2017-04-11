# coding=utf-8
__author__ = 'gshi'

'''
python类的多继承顺序是有类的__mro__属性决定的，可以通过查看类的__mro__属性来知道类的调用顺序和初始化的顺序。值得注意的是，类属性(包括类的方法)的调用顺序是与__mro__的顺序完全一致的，
但是类的初始化顺序正好与__mro__的顺序相反. Python的多继承顺序是深度优先。
'''
class MotherFamily(object):
    first_name = 'Zhang'

    def __int__(self,second_name):
        super(MotherFamily,self).__int__()
        self.second_name = second_name
        print 'Mother class is initializing'

    def print_name(self):
        print 'my name is ' + self.first_name + ' ' + self.second_name


class FatherFamily(object):
    first_name = 'Shi'

    def __init__(self,second_name):
        super(FatherFamily,self).__init__()
        self.second_name = second_name
        # self.age = age
        print 'Father class is initializing'

    def print_name(self):
        print 'my name is ' + self.first_name + ' ' + self.second_name


class MyFamily(MotherFamily,FatherFamily):
    def __int__(self,second_name):
        super(MyFamily,self).__init__(second_name)

# son = MyFamily('haoming')
# son.print_name()


class A(object):
    inheritable = 'inheritable'
    __uninheritable = 'uninheritable'  #__开头的变量是不能被继承的，属于private成员变量
    def __init__(self):
        super(A, self).__init__()
        print "A!"

    def hello(self):
        print 'Hello A!'


class B(object):
    def __init__(self):
        super(B, self).__init__()
        print "B!"

    def hello(self):
        print 'Hello B!'


class AB(A, B):
    def __init__(self):
        super(AB, self).__init__()
        print "AB!"

    # def hello(self):
    #     print 'Hello AB!'


class C(object):
    def __init__(self):
        super(C,  self).__init__()
        print "C!"

    def hello(self):
        print 'Hello C!'


class D(object):
    def __init__(self):
        super(D, self).__init__()
        print "D!"

    def hello(self):
        print 'Hello D!'


class CD(C, D):
    def __init__(self):
        super(CD, self).__init__()
        print "CD!"

    def hello(self):
        print 'Hello CD!'


class ABCD(AB, CD):
    def __init__(self):
        super(ABCD, self).__init__()
        print "ABCD!"

    # def hello(self):
    #     print 'Hello ABCD!'


class E(object):
    def __int__(self):
        super(E,self).__init__()
        print "E!"

    def hello(self):
        print 'Hello E!'


class ABCDE(E,ABCD):
    def __int__(self):
        super(ABCDE,self).__init__()
        print "ABCDE!"

print ABCD.__mro__
print '#'*10
mix = ABCD()
print '#'*10
mix.hello()
print mix.inheritable
print mix.__inheritable
print mix.__doc__
print mix.__class__
print mix.__module__
print mix.__str__
print mix.__dict__


