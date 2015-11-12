import random, string

def makeRandomToken(rbg, length):
    return "".join([rbg.choice(string.hexdigits) for i in xrange(length)])
