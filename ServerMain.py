import sys, json
from twisted.web.server import Site
from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import reactor

from twisted.enterprise import adbapi

import Lobby, Accounts

cp = adbapi.ConnectionPool("sqlite3", "trongame.db", check_same_thread = False)

def createDatabase():
    cp.runQuery(
        """
        create table if not exists accounts (
            id integer primary key autoincrement,
            name text unique,
            pictureUrl text,
            friends text,
            token text,
            currentGame integer default 0
        )
        """
    )
    cp.runQuery(
        """
        create table if not exists games (
            id integer primary key autoincrement,
            name text unique,
            owner integer,
            maxPlayers integer,
            ping integer,
            token text,
            hasStarted boolean
        )
        """
    )

root = Resource()
root.putChild("insertAccount", Accounts.InsertAccount(cp))
root.putChild("showAccount", Accounts.ShowAccount(cp))
#root.putChild("updateAccount", Accounts.UpdateAccount(cp))
root.putChild("insertGame", Lobby.InsertGame(cp))
root.putChild("deleteGame", Lobby.RemoveGame(cp))
root.putChild("joinGame", Lobby.JoinGame(cp))
root.putChild("listGames", Lobby.ListGames(cp))
root.putChild("listPlayers", Lobby.ListPlayers(cp))
factory = Site(root)
reactor.listenTCP(8880, factory)

createDatabase()

reactor.run()
