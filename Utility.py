import random, string
from hashlib import sha256

TOKEN_LENGTH = 64 # In hex characters (hence 128 bits)

def makeRandomToken(rbg, length = TOKEN_LENGTH):
    return "".join([rbg.choice(string.hexdigits) for i in xrange(length)])

def hashToken(token):
    # No need for a KDF since token is high-entropy
    return sha256(token).hexdigest()

def checkToken(token, realTokenHash):
    # Assume side channels (timing attacks) are out of scope
    return hashToken(token) == tokenHash
