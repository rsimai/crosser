#!/usr/bin/python

matrix = 10

def increase(matrix):
    matrix += 1
    return matrix

while 1:
    matrix = increase(matrix)
    print matrix
    if matrix > 100:
        break
