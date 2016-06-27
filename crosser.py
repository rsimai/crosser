#!/usr/bin/python
#
# trying american style first
#

# dimensions
xmax = 20
ymax = 15


# to have some words
with open('/usr/share/dict/american', 'r') as fd:
    wordlist =fd.read().splitlines()


# create the matrix[y][x] from 0,0 to ymax,xmax
matrix = [[" " for x in range(xmax)] for y in range(ymax)] 


def printout():
   for y in range(ymax):
      outline = ""
      for x in range(xmax):
         outline = outline + matrix[y][x]
      print outline




printout()


