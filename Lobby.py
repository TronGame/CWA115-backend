import sys, json
from twisted.web.server import Site
from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.internet import reactor

from twisted.enterprise import adbapi

class InsertGame(Resource):

    def __init__(self, cp):
        self.cp = cp

    def gameInserted(self, result, request):
        request.write(json.dumps(result))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        try:
            name = request.args["name"][0]
            owner = request.args["owner"][0]
            result = self.cp.runQuery(
                "insert or ignore into games (name, owner, ping) values (?, ?, 0)", (name, owner)
            )
            result.addCallback(self.gameInserted, request)
            return NOT_DONE_YET 
        except KeyError:
            return json.dumps({"error" : "not all arguments set"}) 

class ListGames(Resource):

    def __init__(self, cp):
        self.cp = cp

    def gameSelected(self, result, request):
        request.write(json.dumps(result))
        request.finish()

    def render_GET(self, request):
        request.defaultContentType = "application/json"
        result = self.cp.runQuery("select * from games")
        result.addCallback(self.gameSelected, request)
        return NOT_DONE_YET 

