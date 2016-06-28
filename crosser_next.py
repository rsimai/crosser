#!/usr/bin/python

import random
import numpy

boardsize = 10
dictionary = 'wordlist.dict'

matrix = [[" " for x in range(boardsize)] for y in range(boardsize)]

# just for developing, to have some content in the master matrix
matrix[0][0] = "T"
matrix[1][0] = "E"
matrix[2][0] = "S"
matrix[3][0] = "T"


matrix[0][0] = "T"
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

def pick_random_word():
    number_of words = len(wordlist)
    word = wordlist[randint(0, number_of_words)]
    return word



