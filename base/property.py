# encoding = utf-8
class Manager:
    def __init__(self, name):
        self.name = name
        self.age = 33

    def get_name(self):
        return self.name

    def set_name(self, name):
        self.name = name

    name = property(get_name, set_name)  # for both setter and getter, property function looks better than @property

    @property  # for getter only, @property is a good way
    def get_age(self):
        return self.age

    @get_age.setter
    def set_age(self, age):
        self.age = age


m = Manager('Guang Shi')
print m.name  # get_name
m.name = 'gshi'  # set_name
print m.name
print m.get_age  # get_age
m.age = 35  # set_age
print m.get_age  # get_age