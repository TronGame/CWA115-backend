var socket;
var lastTime;
var msgLog = []; 
var gameId = null;

var players = {};
var walls = {};

var bikeIcon = {url : 'icons/bike.png', scaledSize : {width : 48, height : 48}};
var bikeBellIcon = {url : 'icons/bikeWithBell.png', scaledSize : {width : 48, height : 48}};

var currentGameData = [];
var paused = false;

function handleMessage(data) {
    switch(data['type']) {
        case 'updatePosition':
            var newPosition = {lat : data.location.latitude, lng : data.location.longitude};
            if(!players.hasOwnProperty(data.playerId)) {
                players[data.playerId] =  new google.maps.Marker({
                    position : newPosition,
                    map: map,
                    title: data.playerName,
                    icon: bikeIcon
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
        case 'ringBell':
            if(players.hasOwnProperty(data.playerId)) {
                players[data.playerId].setIcon(bikeBellIcon);
                setTimeout(function() { players[data.playerId].setIcon(bikeIcon); }, 3000);
            }
            break;
    }
}

// Snap a user-created polyline to roads and draw the snapped path
function runSnapToRoad(wallId) {
    var path = walls[wallId].getPath();
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

function saveGame() {
    var gameData = new Blob([JSON.stringify(msgLog)], {type : 'text/plain'});
    window.open(URL.createObjectURL(gameData));
}

function setGame() {
    gameId = window.prompt('Game id?', '1');

    // Start listening
    socket = io('http://daddi.cs.kuleuven.be', {path : '/peno3/socket.io'});
		
    lastTime = Date.now();

    socket.emit('register', {groupid : 'testA1', sessionid : gameId});

    socket.on('broadcastReceived', function(data) {
        console.log(data);
        var currentTime = Date.now();
        msgLog.push({data : data, time : currentTime - lastTime});
        lastTime = currentTime;
        handleMessage(data);
    });

    toastr.success('Game set.');
}

function showFileDialog() {
    document.getElementById('loadDialog').click();
}

function loadGame(path) {
    if(path.files && path.files[0]) { 
        var reader = new FileReader();
        reader.onload = function(e) {
            emulateGame(JSON.parse(e.target.result));
        };
        reader.readAsText(path.files[0]);
    }
}

function emulateGame(gameData) {
    var speedUp = window.prompt('Speed up?', '1.0');
    currentGame = {data : gameData, i : 0, speedUp : speedUp};
    setTimeout(function(data) {
        sendNext();
    }, currentGame.data[currentGame.i].time / currentGame.speedUp);
}

function sendNext() {
    if(paused)
        return;

    handleMessage(currentGame.data[currentGame.i].data);
    setTimeout(function(data) {
        ++currentGame.i;
        sendNext();
    }, currentGame.data[currentGame.i].time / currentGame.speedUp);
}

function clearGame() {
    // Remove markers from the map
    for(var k in players) {
        if(players.hasOwnProperty(k))
            players[k].setMap(null);
    }
    for(var k in walls) {
        if(walls.hasOwnProperty(k))
            walls[k].setMap(null);
    }
    players = {};
    walls = {};
    msgLog = [];
    lastTime = Date.now();
    toastr.success('Map cleared.');
}

function pauseReplay() {
    if(!paused) {
        paused = true;
        document.getElementById("pauseButton").innerHTML = "Resume";
    } else {
        paused = false;
        sendNext(currentGame);
        document.getElementById("pauseButton").innerHTML = "Pause";
    }
}
