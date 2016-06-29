#!/usr/bin/python
#
# trying american style first
#

from random import randint
import numpy
import re

# global stuff
# dimensions
max = 11
dictionary = 'wordlist.dict'

# create matrix
matrix = [[" " for x in range(max)] for y in range(max)]
for y in range(max):
    for x in range(max):
        if (x+1)/2 == (x+1)/2.0 and (y+1)/2 == (y+1)/2.0:
            matrix[x][y] = "#"


def load_dictionary():
    with open(dictionary, 'r') as fd:
        wordlist = fd.read().splitlines()
        return wordlist

def printout(mymatrix):
    for y in range(max):
        outline = ""
        for x in range(max):
            outline = outline + mymatrix[x][y]
        print(outline)
    return

def pickword(maxlength):
    wordsleft = len(wordlist)
    if wordsleft < 1:
        return "#"
    tryword = wordlist.pop(randint(0, wordsleft))
    return tryword

def retainword(word):
    wordlist.append(word)

def suggest_coordinates():
    for y in range(max):
        for x in range(max):
            if matrix[x][y] == " ":
                return(x, y, "success")
    return(0, 0, fail)

def find_wordstart(x, y):
    for i in range(x, 0, -1):
        if mymatrix[i][y] == "#":
            xpos = i+1
            for i in range (xpos, max):
                if mymatrix[i][x] == "#"
                    ypos = i
                break
            return(xpos, ypos)
    return (0, x)    

def mirror_matrix(mymatrix):
    mymatrix = numpy.rot90(mymatrix)
    mymatrix = numpy.flipud(mymatrix)
    return(mymatrix)


printout(matrix)
