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

    def insertGame(self, interaction, name, owner, maxPlayers, token, playerToken,
        wallbreaker, timeLimit, maxDist):

        interaction.execute("select token from accounts where id = ?", (owner, ))
        realToken = interaction.fetchone()
        if realToken is None or not Utility.checkToken(playerToken, realToken[0]):
            return None

        interaction.execute(
            """
            insert or ignore into games (
                name, owner, maxPlayers, ping, token, wallbreaker, timeLimit, maxDist
            )
            values (?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (name, owner, maxPlayers, Utility.hashToken(token), wallbreaker, timeLimit, maxDist)
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
            timeLimit = int(request.args.get("timeLimit", [-1])[0])
            maxDist = float(request.args.get("maxDist", [-1])[0])
            token = Utility.makeRandomToken(self.rbg)
            result = self.cp.runInteraction(
                self.insertGame, name, owner, maxPlayers, token,
                playerToken, wallbreaker, timeLimit, maxDist
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

        try:
            identifier = request.args["id"][0]
            result = self.cp.runQuery(
                "delete from games where id = ? and token = ?", (identifier, Utility.hashToken(token))
            )
            result.addCallback(self.gameRemoved, request, token)
            return NOT_DONE_YET
        except KeyError:
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
            "update games set hasStarted = 1 where token = ?", (Utility.hashToken(token),)
        )
        result.addCallback(self.gameJoined, request, token)
        return NOT_DONE_YET 

class ListGames(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp

    def selectGameInfo(self, interaction, listStarted):
        postfix = "where hasStarted = 0" if not listStarted else ""
        interaction.execute(
            """
            select id, name, owner, maxPlayers, wallbreaker, timeLimit, maxDist
            from games
            """ + postfix
        )
        gameInfo = interaction.fetchall()
        result = []
        for game in gameInfo:
            ownerId = game[2]
            interaction.execute("select name from accounts where id = ?", (ownerId, ))
            ownerName = interaction.fetchone()
            interaction.execute("select count() from accounts where currentGame = ?", (game[0], ))
            playerCount = interaction.fetchone()[0]
            if ownerName is not None:
                result.append(game + (ownerName[0], playerCount))
            else:
                result.append(game + ("Unknown", playerCount))
        return result

    def gameSelected(self, result, request):
        request.write(json.dumps([{
            "id"           : int(row[0]),
            "name"         : row[1],
            "owner"        : row[2],
            "maxPlayers"   : int(row[3]),
            "canBreakWall" : int(row[4]),
            "timeLimit"    : int(row[5]),
            "maxDist"      : float(row[6]),
            "ownerName"    : row[7],
            "playerCount"  : int(row[8])
        } for row in result]))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        listStarted = bool(int(request.args.get("listStarted", [0])[0]))
        result = self.cp.runInteraction(self.selectGameInfo, listStarted)
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
                (gameId, playerId, Utility.hashToken(token))
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
        if realToken is None or not Utility.checkToken(token, realToken[0]):
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

class LeaveGame(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp

    def leftGame(self, result, request):
        request.write(json.dumps({"success" : result}))
        request.finish()

    def leaveGame(self, interaction, playerId, token):
        interaction.execute("select token from accounts where id = ?", (playerId, ))
        realToken = interaction.fetchone()
        if realToken is None or not Utility.checkToken(token, realToken[0]):
            return False

        interaction.execute(
            """
            update or ignore accounts set currentGame = 0 where id = ?
            """,
            (playerId, )
        )
        return True

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            playerId = int(request.args["playerId"][0])
            token = request.args["token"][0]
            result = self.cp.runInteraction(
                self.leaveGame, playerId, token
            )
            result.addCallback(self.leftGame, request)
            return NOT_DONE_YET 
        except:
            return json.dumps({"error" : "not all arguments set"})

class EndGame(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp

    def gameEnded(self, result, request):
        request.write(json.dumps({"success" : result}))
        request.finish()

    def endGame(self, interaction, gameId, token, winnerId):
        interaction.execute("select token from games where id = ?", (gameId, ))
        realToken = interaction.fetchone()
        if realToken is None or not Utility.checkToken(token, realToken[0]):
            return False

        # Increase the wins of the winner
        interaction.execute(
            "update accounts set wins = wins + 1, currentGame = 0 where id = ?",
            (winnerId, )
        )
        # Increase the losses of all other players in the game
        interaction.execute(
            """
            update accounts set losses = losses + 1, currentGame = 0 where id = 
            (select id from accounts where currentGame = ?) and id != ? 
            """,
            (gameId, winnerId)
        )

        # TODO: do we want to permanently remove the game?
        # interaction.execute("delete from games where id = ?", (gameId,))
        return True

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            gameId = int(request.args["gameId"][0])
            token = request.args["token"][0]
            winnerId = request.args["winnerId"][0]
            result = self.cp.runInteraction(
                self.endGame, gameId, token, winnerId
            )
            result.addCallback(self.gameEnded, request)
            return NOT_DONE_YET 
        except:
            return json.dumps({"error" : "not all arguments set"})

class AddInvite(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def addInvite(self, interaction, id, token, friends, gameId):
        interaction.execute("select token from accounts where id = ?", (id, ))
        realToken = interaction.fetchone()
        if realToken is None or not Utility.checkToken(token, realToken[0]):
            return False

        for friend in friends:
            interaction.execute("insert or ignore into invites (inviterId, inviteeId, gameId) values (?,?,?)",(id, friend, gameId))

        return True

    def inviteAdded(self, result, request):
        request.write(json.dumps({"success" : result}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            friends = json.loads(request.args["friends"][0])
            gameId = request.args["gameId"][0]
            self.__cp.runInteraction(self.addInvite, id, token, friends, gameId).addCallback(self.inviteAdded, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class DeleteInvite(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def deleteInvite(self, interaction, id, token, inviteId):
        interaction.execute("select token from accounts where id = ?", (id, ))
        realToken = interaction.fetchone()
        if realToken is None or not Utility.checkToken(token, realToken[0]):
            return False

        interaction.execute("delete from invites where id=? and inviteeId=?",(inviteId, id))

        return True

    def inviteDeleted(self, result, request):
        request.write(json.dumps({"success" : result}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            inviteId = request.args["inviteId"][0]
            self.__cp.runInteraction(self.deleteInvite, id, token, inviteId).addCallback(self.inviteDeleted, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class ShowInvites(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def showInvites(self, interaction, id, token):
        interaction.execute("select token from accounts where id = ?", (id, ))
        realToken = interaction.fetchone()
        if realToken is None or not Utility.checkToken(token, realToken[0]):
            return False

        interaction.execute("select id, inviterId, gameId from invites where inviteeId=?",(id,))
        invites = interaction.fetchall()
        result = []
        for invite in invites:
            result.append(json.dumps({"inviteId" : invite[0], "inviterId" : invite[1], "gameId" : invite[2]}))
        return result

    def invitesShown(self, result, request):
        request.write(json.dumps({"invites" : result}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            self.__cp.runInteraction(self.showInvites, id, token).addCallback(self.invitesShown, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})
