import sys, json
from twisted.web.server import Site
from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import reactor

from twisted.enterprise import adbapi

import Lobby

cp = adbapi.ConnectionPool("sqlite3", "trongame.db", check_same_thread = False)

def createDatabase():
    cp.runQuery("create table if not exists accounts (id integer, name text)")
    cp.runQuery(
        "create table if not exists games (id integer primary key autoincrement, "
        + "name text, owner text, ping integer)"
    )

class InsertAccount(Resource):
    def accountInserted(self, result, request):
        request.write(json.dumps({"result" : result}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            name = request.args["name"][0]
            result = cp.runQuery(
                "insert or ignore into accounts (id, name) values (0, ?)", (name, )
            )
            result.addCallback(self.accountInserted, request)
            return NOT_DONE_YET 
        except KeyError:
            return json.dumps({"error" : "not all arguments set"}) 

class ShowAccount(Resource):
    def accountSelected(self, result, request):
        if not result:
            request.write(json.dumps({"error" : "name not found"}))
        else:
            request.write(json.dumps({"id" : result[0][0], "name" : result[0][1]}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            name = request.args["name"][0]
            result = cp.runQuery("select id, name from accounts where name = ?", (name, ))
            result.addCallback(self.accountSelected, request)
            return NOT_DONE_YET 
        except KeyError:
            return json.dumps({"error" : "not all arguments set"}) 

root = Resource()
root.putChild("insertAccount", InsertAccount())
root.putChild("showAccount", ShowAccount())
root.putChild("insertGame", Lobby.InsertGame(cp))
root.putChild("listGames", Lobby.ListGames(cp))

factory = Site(root)
reactor.listenTCP(8880, factory)

createDatabase()

reactor.run()
