import json, random, Utility

from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource

class InsertAccount(Resource):
    def __init__(self, cp):
        Resource.__init__(self)
        self.__cp = cp
        self.rbg = random.SystemRandom()

    def insertAccount(self, interaction, name, pictureUrl, friends, token):
        interaction.execute(
            "insert or ignore into accounts (name,pictureUrl,token) values (?,?,?)",
            (name, pictureUrl, token)
        )
        interaction.execute("select max(id) from accounts")
        userId = interaction.fetchone()[0]

        for friend in friends:
            print friend
            interaction.execute(
                "insert or ignore into friends (id,userId1,userId2) values (null,?,?)", (userId, friend)
            )

        return userId

    def accountInserted(self, id, request, token):
        request.write(json.dumps({"token" : token, "id" : id}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            name = request.args["name"][0]
            pictureUrl = request.args.get("pictureUrl",[""])[0]
            friends = request.args.get("friends",[""])[0]
            token = Utility.makeRandomToken(self.rbg, int(request.args.get("tokenLength", [25])[0]))
            result = self.__cp.runInteraction(self.insertAccount, name, pictureUrl, json.loads(friends), token)
            result.addCallback(self.accountInserted, request, token)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class ShowAccount(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def accountSelected(self, result, request):
        if not result:
            request.write(json.dumps({"error" : "profile not found"}))
            request.finish()
        else:
            id = request.args["id"][0]
            request.write(json.dumps({"id" : result[0][0], "name" : result[0][1], "pictureUrl" : result[0][2]}))
            newResult = self.__cp.runQuery("select userId1, userId2 from friends where userId1=? or userId2=?", (id, id))
            newResult.addCallback(self.friendsSelected, request)

    def friendsSelected(self, result, request):
        if not result:
            request.write(json.dumps({"error" : "no friends found"}))
        else:
            userId = request.args["id"][0]
            friends = []
            for entry in result:
                if int(entry[0])==int(userId):
                    friends.append(entry[1])
                else:
                    friends.append(entry[0])
            request.write(json.dumps({"friends" : friends}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            result = self.__cp.runQuery("select id, name, pictureUrl from accounts where id = ? and token = ?", (id, token))
            result.addCallback(self.accountSelected, request)
            return NOT_DONE_YET 
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class UpdateAccount(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def updateAccount(self, interaction, id, token, newName, newPictureUrl, newFriends):
        if newName is not None:
            interaction.execute("update accounts set name=? where id=? and token=?",(newName,id,token))
        if newPictureUrl is not None:
            interaction.execute("update accounts set pictureUrl=? where id=? and token=?",(newPictureUrl,id,token))
        if newFriends is not None:
            # First delete previous friend records
            interaction.execute("delete from friends where userId1=? or userId2=?",(id,id))
            # Then insert new friends
            for friend in newFriends:
                interaction.execute("insert or ignore into friends (id,userId1,userId2) values (null,?,?)",(id,friend))

    def accountUpdated(self, result, request):
        #if not result:
        #    request.write(json.dumps({"error" : "profile not found"}))
        #else:
        #    request.write(json.dumps({"id" : result[0][0], "name" : result[0][1], "pictureUrl" : result[0][2], "friends" : result[0][3]}))
        request.write(json.dumps({"succes" : True}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            token = request.args["token"][0]
            newName = request.args.get("name",[None])[0]
            newPictureUrl = request.args.get("pictureUrl",[None])[0]
            newFriends = request.args.get("friends",[None])[0]
            result = self.__cp.runInteraction(self.updateAccount, id, token, newName, newPictureUrl, json.loads(newFriends))
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
                results[entry[0]] = {"name" : entry[1], "pictureUrl" : entry[2]}
            request.write(json.dumps({"accounts" : results}))
        self.__cp.runQuery("select * from friends").addCallback(self.friendsSelected, request)

    def friendsSelected(self, result, request):
        if not result:
            request.write(json.dumps({"friends" : {"error" : "friends not found"}}))
        else:
            results = dict()
            for entry in result:
                results[entry[0]] = {"userId1" : entry[1], "userId2" : entry[2]}
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
            result = self.__cp.runQuery("delete from accounts where id=? and token=?", (id, token))
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