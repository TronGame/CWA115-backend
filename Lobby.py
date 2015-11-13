import sys, json, random, Utility
from twisted.web.server import Site
from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import reactor

from twisted.enterprise import adbapi

class InsertGame(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp
        self.rbg = random.SystemRandom()

    def insertGame(self, interaction, name, owner, maxPlayers, token, playerToken):
        interaction.execute("select token from accounts where id = ?", (owner, ))
        realToken = interaction.fetchone()
        if realToken is None or realToken[0] != playerToken:
            return None

        interaction.execute(
            """
            insert or ignore into games (name, owner, maxPlayers, ping, token)
            values (?, ?, ?, 0, ?)
            """,
            (name, owner, maxPlayers, token)
        )
        interaction.execute("select max(id) from games")
        return interaction.fetchone()[0]


    def gameInserted(self, id, request, token):
        if id is None:
            request.write(json.dumps({"error" : "invalid token"}))
        else:
            request.write(json.dumps({"token" : token, "id" : id}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            name = request.args["name"][0]
            playerToken = request.args["token"][0]
            owner = int(request.args["owner"][0])
            maxPlayers = int(request.args["maxPlayers"][0])
            token = Utility.makeRandomToken(self.rbg, int(request.args.get("tokenLength", [25])[0]))
            result = self.cp.runInteraction(
                self.insertGame, name, owner, maxPlayers, token, playerToken
            )
            result.addCallback(self.gameInserted, request, token)
            return NOT_DONE_YET 
        except Exception:
            return json.dumps({"error" : "invalid arguments"})

class RemoveGame(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp

    def gameRemoved(self, result, request, token):
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            token = request.args["token"][0]
        except KeyError:
            return json.dumps({"error" : "no token given"})

        if "name" in request.args:
            name = request.args["name"][0]
            result = self.cp.runQuery(
                "delete from games where name = ? and token = ?", (name, token)
            )
            result.addCallback(self.gameRemoved, request, token)
            return NOT_DONE_YET 
        elif "id" in request.args: 
            identifier = request.args["id"][0]
            result = self.cp.runQuery(
                "delete from games where id = ? and token = ?", (identifier, token)
            )
            result.addCallback(self.gameRemoved, request, token)
            return NOT_DONE_YET
        else:
            return json.dumps({"error" : "id or name required"})

class ListGames(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp

    def gameSelected(self, result, request):
        request.write(json.dumps([{
            "id"         : row[0],
            "name"       : row[1],
            "owner"      : row[2],
            "ping"       : int(row[3]),
            "maxPlayers" : int(row[4])
        } for row in result]))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        result = self.cp.runQuery("select id, name, owner, ping, maxPlayers from games")
        result.addCallback(self.gameSelected, request)
        return NOT_DONE_YET 
