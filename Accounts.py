import json, random, Utility

from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from sqlite3 import IntegrityError

class InsertAccount(Resource):
    def __init__(self, cp):
        Resource.__init__(self)
        self.__cp = cp
        self.rbg = random.SystemRandom()

    def insertAccount(self, interaction, name, pictureUrl, friends, facebookId, token):
        try:
            interaction.execute(
                "insert or fail into accounts (name,pictureUrl,token) values (?,?,?)",
                (name, pictureUrl, Utility.hashToken(token))
            )
            interaction.execute("select max(id) from accounts")
            userId = interaction.fetchone()[0]

            if facebookId is not None:
                interaction.execute("update accounts set facebookId=? where id=?", (facebookId, userId))

            for friend in friends:
                interaction.execute(
                    "insert or ignore into friends (id,userId1,userId2,pending) values (null,?,?,0)", (userId, friend)
                )

            return userId
        except IntegrityError:
            return None

    def accountInserted(self, id, request, token):
        if id is None:
            request.write(json.dumps({"error" : "profile already exists"}))
        else:
            request.write(json.dumps({"token" : token, "id" : id}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            name = request.args["name"][0]
            pictureUrl = request.args.get("pictureUrl",[""])[0]
            friends = request.args.get("friends",["[]"])[0]
            facebookId = request.args.get("facebookId",[None])[0]
            token = Utility.makeRandomToken(self.rbg)
            result = self.__cp.runInteraction(self.insertAccount, name, pictureUrl, json.loads(friends), facebookId, token)
            result.addCallback(self.accountInserted, request, token)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class ShowAccount(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def accountSelected(self, result, request, authorized):
        if not result:
            request.write(json.dumps({"error" : "profile not found"}))
            request.finish()
        else:
            id = request.args["id"][0]
            if authorized:
                newResult = self.__cp.runQuery("select userId1, userId2, pending, commonPlays from friends where userId1=? or userId2=?", (id, id))
                newResult.addCallback(self.friendsSelected, request, result[0])
            else:
                request.write(json.dumps({"id" : result[0][0],
                                          "facebookId" : result[0][1],
                                          "name" : result[0][2],
                                          "pictureUrl" : result[0][3],
                                          "wins" : result[0][4],
                                          "losses" : result[0][5],
                                          "highscore" : result[0][6]}))
                request.finish()

    def friendsSelected(self, result, request, account):
        if not result:
            result = [] # empty friends list
        userId = request.args["id"][0]
        friends = []
        for entry in result:
            if int(entry[0])==int(userId):
                friends.append(json.dumps({"id" : entry[1], "accepted" : 1-int(entry[2]), "commonPlays" : entry[3]}))
            else:
                friends.append(json.dumps({"id" : entry[0], "pending" : entry[2], "commonPlays" : entry[3]}))
        request.write(json.dumps({"id" : account[0],
                                  "facebookId" : account[1],
                                  "name" : account[2],
                                  "pictureUrl" : account[3],
                                  "wins" : account[4],
                                  "losses" : account[5],
                                  "highscore" : account[6],
                                  "playtime" : account[7],
                                  "friends" : friends}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args.get("token",[None])[0]
            if token is None:
                result = self.__cp.runQuery("select id, facebookId, name, pictureUrl, wins, losses, highscore from accounts where id = ?", (id,))
                result.addCallback(self.accountSelected, request, False)
            else:
                result = self.__cp.runQuery("select id, facebookId, name, pictureUrl, wins, losses, highscore, playtime from accounts where id = ? and token = ?", (id, Utility.hashToken(token)))
                result.addCallback(self.accountSelected, request, True)
            return NOT_DONE_YET 
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class UpdateAccount(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def updateAccount(self, interaction, id, token, newName, newPictureUrl):
        interaction.execute("select token from accounts where id = ?", (id, ))
        result = interaction.fetchone()
        if result is None or not Utility.checkToken(token, result[0]):
            return False

        if newName is not None:
            interaction.execute("update accounts set name=? where id=?",(newName,id))
        if newPictureUrl is not None:
            interaction.execute("update accounts set pictureUrl=? where id=?",(newPictureUrl,id))

        return True

    def accountUpdated(self, result, request):
        request.write(json.dumps({"success" : result}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            newName = request.args.get("name",[None])[0]
            newPictureUrl = request.args.get("pictureUrl",[None])[0]
            result = self.__cp.runInteraction(self.updateAccount, id, token, newName, newPictureUrl)
            result.addCallback(self.accountUpdated, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class ShowAll(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def accountsSelected(self, result, request):
        if not result:
            request.write(json.dumps({"accounts" : {"error" : "profile not found"}}))
        else:
            results = dict()
            for entry in result:
                results[entry[0]] = {"name" : entry[3],
                                     "pictureUrl" : entry[4],
                                     "facebookId" : entry[2],
                                     "wins" : entry[5],
                                     "losses" : entry[6],
                                     "highscore" : entry[7],
                                     "playtime" : entry[8]}
            request.write(json.dumps({"accounts" : results}))
        self.__cp.runQuery("select * from friends").addCallback(self.friendsSelected, request)

    def friendsSelected(self, result, request):
        if not result:
            request.write(json.dumps({"friends" : {"error" : "friends not found"}}))
        else:
            results = dict()
            for entry in result:
                results[entry[0]] = {"userId1" : entry[1], "userId2" : entry[2], "pending" : entry[3], "commonPlays" : entry[4]}
            request.write(json.dumps({"friends" : results }))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            result = self.__cp.runQuery("select * from accounts")
            result.addCallback(self.accountsSelected, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class DeleteAccount(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def accountDeleted(self, result, request):
        id = request.args["id"][0]
        self.__cp.runQuery("delete from friends where userId1=? or userId2=?", (id,id))
        request.write(json.dumps({"success" : True}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            result = self.__cp.runQuery("delete from accounts where id=? and token=?", (id, Utility.hashToken(token)))
            result.addCallback(self.accountDeleted, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class clearAll(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def accountsDeleted(self, result, request):
        request.write(json.dumps({"accountDeletionSuccess" : True}))
        self.__cp.runQuery("delete from friends").addCallback(self.friendsDeleted, request)

    def friendsDeleted(self, result, request):
        request.write(json.dumps({"friendsDeletionSuccess" : True}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            result = self.__cp.runQuery("delete from accounts")
            result.addCallback(self.accountsDeleted, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class GetFriendIds(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp
        self.__friends = []
        self.__friendsCount = 0

    def friendSelected(self, result, request):
        # Fix problem when facebook user has authorized app, but isn't registered on our server:
        if len(result)==0:
            self.__friendsCount -= 1
        else:
            self.__friends.append(result[0][0])
        if len(self.__friends)==self.__friendsCount:
            request.write(json.dumps({"friends" : json.dumps(self.__friends)}))
            request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            self.__friends = []
            facebookIds = json.loads(request.args["facebookIds"][0])
            if len(facebookIds)==0:
                return json.dumps({"friends" : json.dumps([])})
            self.__friendsCount = len(facebookIds)
            for facebookId in facebookIds:
                self.__cp.runQuery("select id from accounts where facebookId=?",(long(facebookId),)).addCallback(self.friendSelected, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class ScoreBoard(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp

    def selectPlayerScores(self, interaction):
        interaction.execute("select id, name, pictureUrl from accounts")
        result = []
        for account in interaction.fetchall():
            interaction.execute("select count() from games where winner = ?", (account[0], ))
            gamesWon = interaction.fetchone()
            gamesWon = 0 if gamesWon is None else gamesWon[0]
            result.append((account[0], account[1], account[2], gamesWon))

        return sorted(result, cmp = lambda x, y : cmp(y[-1], x[-1]))

    def scoresSelected(self, result, request):
        request.write(json.dumps([{
            "id"           : int(row[0]),
            "name"         : row[1],
            "pictureUrl"   : row[2],
            "gamesWon"     : int(row[3]),
        } for row in result]))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        result = self.cp.runInteraction(self.selectPlayerScores)
        result.addCallback(self.scoresSelected, request)
        return NOT_DONE_YET

class IncreaseWins(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def winsIncreased(self, result, request):
        request.write(json.dumps({"success" : True}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            self.__cp.runQuery("update accounts set wins = wins + 1 where id=? and token=?",(id, Utility.hashToken(token))).addCallback(self.winsIncreased, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class IncreaseLosses(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def lossesIncreased(self, result, request):
        request.write(json.dumps({"success" : True}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            self.__cp.runQuery("update accounts set losses = losses + 1 where id=? and token=?",(id, Utility.hashToken(token))).addCallback(self.lossesIncreased, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class IncreaseCommonPlays(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def commonPlaysIncreased(self, result, request):
        request.write(json.dumps({"success" : result}))
        request.finish()

    def increaseCommonPlays(self, interaction, userId, token, friendId):
        interaction.execute("select token from accounts where id = ?", (userId, ))
        realToken = interaction.fetchone()
        if realToken is None or not Utility.checkToken(token, realToken[0]):
            return False
        interaction.execute("update friends set commonPlays = commonPlays + 1 where userId1=? and userId2=?",(userId, friendId))

        return True

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            friendId = request.args["friendId"][0]
            self.__cp.runInteraction(self.increaseCommonPlays, id, token, friendId).addCallback(self.commonPlaysIncreased, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class SetHighscore(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def highscoreUpdated(self, result, request):
        request.write(json.dumps({"success" : True}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            highscore = int(request.args["highscore"][0])
            self.__cp.runQuery("update accounts set highscore = ? where id=? and token=?",(highscore, id, Utility.hashToken(token))).addCallback(self.highscoreUpdated, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class SetPlaytime(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def playtimeUpdated(self, result, request):
        request.write(json.dumps({"success" : True}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            playtime = int(request.args["playtime"][0])
            self.__cp.runQuery("update accounts set playtime = ? where id=? and token=?",(playtime, id, Utility.hashToken(token))).addCallback(self.playtimeUpdated, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class AddFriends(Resource): #userId1 is the one who sent the friend request

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def addFriends(self, interaction, id, token, friends, pending):
        interaction.execute("select token from accounts where id = ?", (id, ))
        realToken = interaction.fetchone()
        if realToken is None or not Utility.checkToken(token, realToken[0]):
            return False

        for friend in friends:
            interaction.execute("insert or ignore into friends (userId1, userId2, pending) values (?,?,?)",(id, friend, pending))

        return True

    def friendsAdded(self, result, request):
        request.write(json.dumps({"success" : result}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            friends = json.loads(request.args["friends"][0])
            pending = 1-int(request.args.get("accepted",[0])[0])
            self.__cp.runInteraction(self.addFriends, id, token, friends, pending).addCallback(self.friendsAdded, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class DeleteFriend(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def deleteFriend(self, interaction, id, token, friend):
        interaction.execute("select token from accounts where id = ?", (id, ))
        realToken = interaction.fetchone()
        if realToken is None or not Utility.checkToken(token, realToken[0]):
            return False

        interaction.execute("delete from friends where (userId1=? and userId2=?) or (userId1=? and userId2=?)",(id, friend, friend, id))

        return True

    def friendDeleted(self, result, request):
        request.write(json.dumps({"success" : result}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            friend = request.args["friendId"][0]
            self.__cp.runInteraction(self.deleteFriend, id, token, friend).addCallback(self.friendDeleted, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class AcceptFriend(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def acceptFriend(self, interaction, id, token, friend):
        interaction.execute("select token from accounts where id = ?", (id, ))
        realToken = interaction.fetchone()
        if realToken is None or not Utility.checkToken(token, realToken[0]):
            return False

        interaction.execute("update friends set pending = 0 where userId1=? and userId2=?",(friend, id))
        # Only the other player (userId2) can accept the pending friend request

        return True

    def friendAccepted(self, result, request):
        request.write(json.dumps({"success" : result}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            friend = request.args["friendId"][0]
            self.__cp.runInteraction(self.acceptFriend, id, token, friend).addCallback(self.friendAccepted, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})
