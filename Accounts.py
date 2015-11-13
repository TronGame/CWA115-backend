import json, random, Utility

from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource

class InsertAccount(Resource):
    def __init__(self, cp):
        Resource.__init__(self)
        self.__cp = cp
        self.rbg = random.SystemRandom()

    def accountInserted(self, result, request, token):
        request.write(json.dumps({"token" : token}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            name = request.args["name"][0]
            pictureUrl = request.args.get("pictureUrl",[""])[0]
            friends = request.args.get("friends",[""])[0]
            token = Utility.makeRandomToken(self.rbg, int(request.args.get("tokenLength", [25])[0]))
            result = self.__cp.runQuery(
                "insert or ignore into accounts (name,pictureUrl,friends, token) values (?,?,?,?)",
                (name, pictureUrl, friends, token)
            )
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
        else:
            request.write(json.dumps({"id" : result[0][0], "name" : result[0][1], "pictureUrl" : result[0][2], "friends" : result[0][3]}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            result = self.__cp.runQuery("select id, name, pictureUrl, friends from accounts where id = ?", (id, ))
            result.addCallback(self.accountSelected, request)
            return NOT_DONE_YET 
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class UpdateAccount(Resource):

    def __init__(self,cp):
        Resource.__init__(self)
        self.__cp = cp

    def accountUpdated(self, result, request):
        #if not result:
        #    request.write(json.dumps({"error" : "profile not found"}))
        #else:
        #    request.write(json.dumps({"id" : result[0][0], "name" : result[0][1], "pictureUrl" : result[0][2], "friends" : result[0][3]}))
        request.write(json.dumps(request))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            id = request.args["id"][0]
            update_fields = self.getUpdateFields(request.args,["name","pictureUrl","friends"])
            result = self.__cp.runQuery("update accounts set " + update_fields + " where id = ?", (id, ))
            result.addCallback(self.accountUpdated, request)
            return NOT_DONE_YET
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

    def getUpdateFields(self,requestArgs,fields):
        update_fields = []
        for field in fields:
            update_field = requestArgs.get(field,None)
            if update_field is not None:
                update_fields.append(field + '="' + update_field[0] + '"')
        update_query=", ".join(update_fields)
        print update_query
        return update_query
