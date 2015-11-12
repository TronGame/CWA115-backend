import sys, json
from twisted.web.server import Site
from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import reactor

from twisted.enterprise import adbapi

from Accounts import *

cp = adbapi.ConnectionPool("sqlite3", "trongame.db", check_same_thread = False)

def createDatabase():
    cp.runQuery("create table if not exists accounts (id integer primary key autoincrement, name text, pictureUrl text, friends text)")

root = Resource()
root.putChild("insertAccount", InsertAccount(cp))
root.putChild("showAccount", ShowAccount(cp))
#root.putChild("updateAccount", UpdateAccount(cp))
factory = Site(root)
reactor.listenTCP(8880, factory)

createDatabase()

reactor.run()
