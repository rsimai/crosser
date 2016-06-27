#!/usr/bin/python
#
# trying american style first
#

from random import randint

# dimensions
xmax = 20
ymax = 15
dictionary = '/usr/share/dict/american'
orientation = 'right'

# just for developing
#matrix[0][0] = "T"
#matrix[1][0] = "E"
#matrix[2][0] = "S"
#matrix[3][0] = "T"
#
#matrix[6][0] = "D"
#matrix[6][1] = "R"
#matrix[6][2] = "I"
#matrix[6][3] = "V"
#matrix[6][4] = "E"

def create_matrix():
   matrix = [[" " for x in range(xmax)] for y in range(ymax)]

def load_dictionary():
   with open(dictionary, 'r') as fd:
      wordlist = fd.read().splitlines()
      return wordlist

def printout():
   for y in range(ymax):
      outline = ""
      for x in range(xmax):
         outline = outline + matrix[y][x]
      print outline

def pickword():
   wordsleft = len(wordlist)
   tryword = wordlist[randint(0, wordsleft)]
   return tryword

def suggest_coordinates(matrix):
   for y in range(ymax):
      for x in range(xmax):
         if matrix[y][x] == " ":
            return(y, x)




