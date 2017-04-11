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



