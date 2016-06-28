#!/usr/bin/python
#
# trying american style first
#

from random import randint
import numpy
import re

# global stuff
# dimensions
xmax = 10
ymax = 10
dictionary = 'wordlist.dict'

matrix = [[" " for x in range(xmax)] for y in range(ymax)]

# just for developing, to have some content in the master matrix
matrix[0][0] = "T"
matrix[1][0] = "E"
matrix[2][0] = "S"
matrix[3][0] = "T"

matrix[0][1] = "R"
matrix[0][2] = "A"
matrix[0][3] = "I"
matrix[0][4] = "N"
matrix[0][5] = "S"
matrix[0][6] = "T"
matrix[0][7] = "A"
matrix[0][8] = "T"
matrix[0][9] = "I"


matrix[6][0] = "D"
matrix[6][1] = "R"
matrix[6][2] = "I"
matrix[6][3] = "V"
matrix[6][4] = "E"


def load_dictionary():
    with open(dictionary, 'r') as fd:
        wordlist = fd.read().splitlines()
        return wordlist

def printout(mymatrix):
    for y in range(ymax):
        outline = ""
        for x in range(xmax):
            outline = outline + mymatrix[x][y]
        print(outline)
    return

def pickword():
    wordsleft = len(wordlist)
    tryword = wordlist[randint(0, wordsleft)]
    return tryword

def suggest_coordinates():
    for y in range(ymax):
        for x in range(xmax):
            if matrix[y][x] == " ":
                return(x, y)
    all_done()

def suggest_direction():
    if randint(0, 1) == 0:
        direction = -1 
    else:
        direction = +1
    return(direction)

def find_wordstart(mymatrix, x, y):
    for i in range(y, 0, -1):
        if mymatrix[i][x] == "#":
            return(i+1, x)
    return (0, x)    

def mirror_matrix(mymatrix):
    mymatrix = numpy.rot90(mymatrix)
    mymatrix = numpy.flipud(mymatrix)
    return(mymatrix)

def check_surroundings(mymatrix, x, y):
    if x > 0: 
        if mymatrix[x-1][y] != " " and mymatrix[x-1][y] != "#":
            return(1)
    if x < (xmax-1):
        if mymatrix[x+1][y] != " " and mymatrix[x+1][y] != "#":
            return(1)
    if y > 0:
        if mymatrix[y-1][y] != " " and mymatrix[y-1][y] != "#":
            return(1)
    if y < (ymax - 1):
        if mymatrix[y+1][y] != " " and mymatrix[y+1][y] != "#":
            return(1)
    return(0)



def all_done(mymatrix):
    printout(mymatrix)
    exit


def main_loop(mymatrix, x, y):
    print "DEBUG: start main_loop"
    printout(mymatrix)
    mirrored = 0
    if x < 0 or y < 0:
        print "DEBUG: we'll need coordinates"
        x, y = suggest_coordinates()
        print "DEBUG: start at x, y:", x, y
    direction = suggest_direction()
    print "DEBUG: we'll go", direction
    if direction == -1:
        mymatrix = mirror_matrix(mymatrix)
        mirrored = 1
    find_wordstart(mymatrix, x, y)
    print "we'll start the word at x, y:", x, y
    word = pickword()
    print "DEBUG: use the word:", word
    matrix_backup = mymatrix
    counter = -1
    fail = 0
    for wordletter in word:
        counter += 1
        xpos = x + counter
        print "DEBUG: checking position x, y:", xpos, y
        if xpos >= xmax:
            fail = 1
            print "DEBUG: not enough space here, word too long"
            break
        if mymatrix[xpos][y] == " ":
            mymatrix[counter][y] = wordletter
            print "DEBUG: field was free, now checking surroundings"
            follow_up_required = check_surroundings(mymatrix, xpos, y)
            if follow_up_required == 1:
                mymatrix = main_loop(mymatrix, xpos, y)
        elif mymatrix[xpos][y] == "#":
            print "DEBUG: not enough space here, hit a black block"
            fail = 1
            break

    # fail
    if fail == 1:
        print "doesn't fit, return with the unmodified matrix from before"
        return(matrix_backup, x, y)

    # return
    if mirrored == 1:
        mymatrix = mirror_matrix(mymatrix)
        print "DEBUG: mirror back"
    return(mymatrix)
      


wordlist = load_dictionary()

matrix = main_loop(matrix, -1, -1)

print "let's finish..."

printout(matrix)

print "done!"
