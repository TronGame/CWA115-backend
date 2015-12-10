from twisted.web.static import File
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor

from twisted.enterprise import adbapi

import Games, Accounts

cp = adbapi.ConnectionPool("sqlite3", "trongame.db", check_same_thread = False)

def createDatabase():
    cp.runQuery(
        """
        create table if not exists accounts (
            id integer primary key autoincrement,
            token text,
            facebookId integer,
            name text,
            pictureUrl text,
            wins integer default 0,
            losses integer default 0,
            highscore integer default 0,
            playtime integer default 0,
            currentGame integer default 0
        )
        """
    )
    cp.runQuery(
        """
        create table if not exists games (
            id integer primary key autoincrement,
            name text,
            owner integer,
            maxPlayers integer,
            ping integer,
            token text,
            wallbreaker integer,
            timeLimit integer,
            maxDist float, 
            hasStarted integer default 0
        )
        """
    )
    cp.runQuery(
        """
        create table if not exists friends (
            id integer primary key autoincrement,
            userId1 integer,
            userId2 integer,
            pending integer default 1,
            commonPlays integer default 0,
            unique(userId1, userId2)
        )
        """
    )
    cp.runQuery(
        """
        create table if not exists invites (
            id integer primary key autoincrement,
            inviterId integer,
            inviteeId integer,
            gameId integer,
            unique(inviteeId, gameId)
        )
        """
    )

root = Resource()
# name => (string) New player's name ; pictureUrl => (string) Url to player's profile picture ; friends => (Array [])
# The player's friends' userIds ; tokenLength => (integer) length of token to be created (default=25)
root.putChild("insertAccount", Accounts.InsertAccount(cp))
# id => (integer) Player's id ; token => (integer) Player's token
root.putChild("showAccount", Accounts.ShowAccount(cp))
# id => (integer) Player's id ; token => (integer) Player's token ; params => see insertAccount for available parameters
root.putChild("updateAccount", Accounts.UpdateAccount(cp))
# id => (integer) Player's id ; token => (integer) Player's token
root.putChild("deleteAccount", Accounts.DeleteAccount(cp))
# name => (string) Room name ; token => (integer) Owner's token ; owner => (integer) userId of owner ; maxPlayers =>
# (integer) Maximum number of players ; tokenLength => (integer) length of token to be created (default=25)
root.putChild("insertGame", Games.InsertGame(cp))
# id => (integer) Room id OR name => (string) Room name ; token => (integer) Room token
root.putChild("deleteGame", Games.RemoveGame(cp))
# gameId => (integer) Room id ; id => (integer) Player id ; token => (integer) Player token
root.putChild("startGame", Games.StartGame(cp))
root.putChild("joinGame", Games.JoinGame(cp))
root.putChild("listGames", Games.ListGames(cp))
root.putChild("showGame", Games.ShowGame(cp))
root.putChild("kickPlayer", Games.KickPlayer(cp))
root.putChild("leaveGame", Games.LeaveGame(cp))
root.putChild("endGame", Games.EndGame(cp))
root.putChild("getFriendIds", Accounts.GetFriendIds(cp))
root.putChild("scoreboard", Accounts.ScoreBoard(cp))
root.putChild("increaseCommonPlays", Accounts.IncreaseCommonPlays(cp))
root.putChild("setHighscore", Accounts.SetHighscore(cp))
root.putChild("setPlaytime", Accounts.SetPlaytime(cp))
root.putChild("addFriends", Accounts.AddFriends(cp))
root.putChild("deleteFriend", Accounts.DeleteFriend(cp))
root.putChild("acceptFriend", Accounts.AcceptFriend(cp))
root.putChild("addInvite", Games.AddInvite(cp))
root.putChild("deleteInvite", Games.DeleteInvite(cp))
root.putChild("showInvites", Games.ShowInvites(cp))

# For debugging purposes only:
#root.putChild("showAll", Accounts.ShowAll(cp))
#root.putChild("clearAll", Accounts.ShowAll(cp))

root.putChild("panel", File("panel.html"))
root.putChild("panel.js", File("panel.js"))
icons = Resource()
icons.putChild("bike.png", File("icons/bike.png"))
icons.putChild("bikeWithBell.png", File("icons/bikeWithBell.png"))
root.putChild("icons", icons)

factory = Site(root)
reactor.listenTCP(8880, factory)
createDatabase()

reactor.run()
