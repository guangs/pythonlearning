#!/usr/bin/python
# _*_ coding:utf-8 _*_

#############################################################
# Skills - Consider	Generators	Instead	of	Returning	Lists
#############################################################

# Old : returning a list
def index_words_old(text):
    result = []
    if text:
        result.append(0)
    for index, letter in enumerate(text):
        if letter == ' ':
            result.append(index + 1)
    return result

address = 'Four score and seven years ago...'
results_list = index_words_old(address)
print results_list

# New: use generator to return a iterator
# iterator can be converted a list by passing it to the list build-in function:
# list(results_iterator)
def index_words_new(text):
    if text:
        yield 0
    for index, letter in enumerate(text):
        if letter == ' ':
            yield index + 1

address = 'Four score and seven years ago...'
results_iterator = index_words_new(address)  # this results_iterator is a iterator
for item in results_iterator:
    print item
# what is the upside of New?
# 1. Much easier to read, and iterator returned by generator can easily be converted a list
# 2. For huge inputs, returning list requires a lot of memory, this can cause your program to
#    run out of memory and crash. In contrast, generator and iterator can be easily adapted to
#    take input of arbitrary length


#############################################################
# Skills - Prefer Exception to returning None
#############################################################

# Throwing out Exception when function did not run successfully instead of returning a special
# value such as None to indicate the failure of function.



#############################################################
# Skills - Know	How Closures Interact with Variable Scope
#############################################################

# If a variable in the closure needs interact with the function in which the closure is defined, that
# variable should not be re-define or override by the closure, the variable should be defined in the
# outer function, and be used by the closure.

# in this function, found variable is overrided by the helper, so it is not a interactive variable
# it will not work as we expected
def	sort_priority1(numbers,	group):
    found =	False
    def	helper(x):
        if x in group:
            found = True		# Seems	simple
            return (0,x)
        return (1,x)
    numbers.sort(key=helper)
    return found

# This is the correct way, in this way, found is not defined in helper function, helper function just
# use found variable that was defined in outer function
def	sort_priority2(numbers,	group):
    found =	[False]
    def	helper(x):
        if x in group:
            found[0] = True		# Seems	simple
            return (0,x)
        return (1,x)
    numbers.sort(key=helper)
    return found[0]