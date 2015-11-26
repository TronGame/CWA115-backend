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

    def insertGame(self, interaction, name, owner, maxPlayers, token, playerToken, wallbreaker):
        interaction.execute("select token from accounts where id = ?", (owner, ))
        realToken = interaction.fetchone()
        if realToken is None or realToken[0] != playerToken:
            return None

        interaction.execute(
            """
            insert or ignore into games (name, owner, maxPlayers, ping, token, wallbreaker)
            values (?, ?, ?, 0, ?, ?)
            """,
            (name, owner, maxPlayers, token, wallbreaker)
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
            wallbreaker = int(request.args["canBreakWall"][0])
            token = Utility.makeRandomToken(self.rbg, int(request.args.get("tokenLength", [25])[0]))
            result = self.cp.runInteraction(
                self.insertGame, name, owner, maxPlayers, token, playerToken, wallbreaker
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

class StartGame(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp

    def gameJoined(self, result, request, token):
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            token = request.args["token"][0]
        except KeyError:
            return json.dumps({"error" : "no token given"})

        result = self.cp.runQuery(
            "update games set hasStarted = 1 where token = ?", (token,)
        )
        result.addCallback(self.gameJoined, request, token)
        return NOT_DONE_YET 

class ListGames(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp

    def selectGameInfo(self, interaction):
        interaction.execute(
            "select id, name, owner, maxPlayers, wallbreaker from games where hasStarted = 0"
        )
        gameInfo = interaction.fetchall()
        result = []
        for game in gameInfo:
            ownerId = game[2]
            interaction.execute("select name from accounts where id = ?", (ownerId, ))
            result.append(game + (interaction.fetchone()[0], ))
        return result

    def gameSelected(self, result, request):
        request.write(json.dumps([{
            "id"           : int(row[0]),
            "name"         : row[1],
            "owner"        : row[2],
            "maxPlayers"   : int(row[3]),
            "canBreakWall" : int(row[4]),
            "ownerName"    : row[5]
        } for row in result]))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        result = self.cp.runInteraction(self.selectGameInfo)
        result.addCallback(self.gameSelected, request)
        return NOT_DONE_YET 

class JoinGame(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp

    def gameJoined(self, result, request):
        request.write(json.dumps({"result" : result}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            # TODO: check if the game actually exists
            gameId = int(request.args["gameId"][0])
            playerId = int(request.args["id"][0])
            token = request.args["token"][0]
            result = self.cp.runQuery(
                """
                update or ignore accounts set currentGame = ?
                where id = ? and token = ?
                """,
                (gameId, playerId, token)
            )
            result.addCallback(self.gameJoined, request)
            return NOT_DONE_YET 
        except:
            return json.dumps({"error" : "not all arguments set"})

class ShowGame(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp

    def gameInfoSelected(self, (players, gameInfo) , request):
        if gameInfo is None:
            request.write(json.dumps({"error" : "no such game"}))
            request.finish()
            return

        ownerId = gameInfo[0]
        hasStarted = bool(gameInfo[1])

        playerArray = [{
            "id"         : int(row[0]),
            "name"       : row[1],
            "pictureUrl" : row[2],
        } for row in players]
        request.write(json.dumps({
            "players"    : playerArray,
            "ownerId"    : ownerId,
            "hasStarted" : hasStarted
        }))
        request.finish()

    def selectGameInfo(self, interaction, gameId):
        interaction.execute(
            """
            select id, name, pictureUrl from accounts
            where currentGame = ?
            """,
            (gameId, )
        )

        players = interaction.fetchall()
        interaction.execute("select owner, hasStarted from games where id = ?", (gameId, ))
        gameInfo = interaction.fetchone()
        return players, gameInfo


    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            gameId = int(request.args["gameId"][0])
            result = self.cp.runInteraction(
                self.selectGameInfo, gameId
            )
            result.addCallback(self.gameInfoSelected, request)
            return NOT_DONE_YET 
        except:
            return json.dumps({"error" : "not all arguments set"})

class KickPlayer(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp

    def playerKicked(self, result, request):
        request.write(json.dumps({"success" : result}))
        request.finish()

    def kickPlayer(self, interaction, gameId, playerId, token):
        interaction.execute("select token from games where id = ?", (gameId, ))
        realToken = interaction.fetchone()
        if realToken is None or realToken[0] != token:
            return False

        interaction.execute(
            """
            update or ignore accounts set currentGame = 0
            where id = ? and currentGame = ?
            """,
            (playerId, gameId)
        )
        return True

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            gameId = int(request.args["gameId"][0])
            playerId = int(request.args["playerId"][0])
            token = request.args["token"][0]
            result = self.cp.runInteraction(
                self.kickPlayer, gameId, playerId, token
            )
            result.addCallback(self.playerKicked, request)
            return NOT_DONE_YET 
        except:
            return json.dumps({"error" : "not all arguments set"})
