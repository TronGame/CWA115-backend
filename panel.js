var players = {};
var walls = {};

function handleMessage(data) {
    switch(data['type']) {
        case 'updatePosition':
            var newPosition = {lat : data.location.latitude, lng : data.location.longitude};
            if(!players.hasOwnProperty(data.playerId)) {
                players[data.playerId] =  new google.maps.Marker({
                    position : newPosition,
                    map: map,
                    title: data.playerName
                });
            } else {
                // Update the marker position
                players[data.playerId].setPosition(newPosition);
            }
            break;
        case 'createWall':
            // TODO: fix this on the Java side (send a hex string instead of a signed integer)
            var colorValue = (data.color > 0) ? data.color : 4294967296 + data.color;
            walls[data.wallId] = new google.maps.Polyline({
                path : [],
                strokeColor : '#' + colorValue.toString(16),
                strokeOpacity : 1.0,
                strokeWeight : 15,
                map : map
            });
            runSnapToRoad(data.wallId)
            break;
        case 'updateWall':
            // Walls that were created before joining cannot be displayed
            if(walls.hasOwnProperty(data.wallId)) {
                walls[data.wallId].getPath().push(
                    new google.maps.LatLng(data.point.latitude, data.point.longitude)
                );
                runSnapToRoad(data.wallId)
            }
            break;
    }
}

// Snap a user-created polyline to roads and draw the snapped path
function runSnapToRoad(wallId) {
    var path = walls[data.wallId].getPath();
    var pathValues = [];
    for (var i = 0; i < path.getLength(); i++) {
        pathValues.push(path.getAt(i).toUrlValue());
    }

    var request = new XMLHttpRequest();
    request.open(
        'GET', 'https://roads.googleapis.com/v1/snapToRoads?interpolate=true&key='
         + apiKey + '&path=' + pathValues.join('|'),
        function(data) {
            walls[wallId].setPath(processSnapToRoadResponse(data));
        }
    );
}

// Store snapped polyline returned by the snap-to-road method.
function processSnapToRoadResponse(data) {
    var snappedCoordinates = [];
    for (var i = 0; i < data.snappedPoints.length; i++) {
        var latlng = new google.maps.LatLng(
            data.snappedPoints[i].location.latitude,
            data.snappedPoints[i].location.longitude
        );
        snappedCoordinates.push(latlng);
    }
    return snappedCoordinates;
}
