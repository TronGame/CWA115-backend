import sys, json, random, string
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

    def makeRandomToken(self, length):
        return "".join([self.rbg.choice(string.hexdigits) for i in xrange(length)])

    def gameInserted(self, result, request, token):
        request.write(json.dumps({"result" : result, "token" : token}))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            name = request.args["name"][0]
            owner = request.args["owner"][0]
            token = self.makeRandomToken(int(request.args.get("tokenLength", [25])[0]))
            result = self.cp.runQuery(
                "insert or ignore into games (name, owner, ping) values (?, ?, 0)",
                (name, owner)
            )
            result.addCallback(self.gameInserted, request, token)
            return NOT_DONE_YET 
        except KeyError:
            return json.dumps({"error" : "not all arguments set"})

class ListGames(Resource):

    def __init__(self, cp):
        Resource.__init__(self)
        self.cp = cp

    def gameSelected(self, result, request):
        request.write(json.dumps(
            [{"id" : row[0], "name" : row[1], "owner" : row[2], "ping" : row[3]}\
            for row in result]
        ))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        result = self.cp.runQuery("select id, name, owner, ping from games")
        result.addCallback(self.gameSelected, request)
        return NOT_DONE_YET 

