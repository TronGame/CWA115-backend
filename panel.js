var socket;
var lastTime;
var msgLog = []; 
var gameId = null;

var players = {};
var walls = {};
var border;

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
        case 'playerDead':
            if (data.playerKillerId == "")
                toastr.error("Player "+data.playerName+", has died.");
            else {
                toastr.error(
                    "Player "+data.playerName+ ", was killed by "+data.playerKillerName + "."
                );
            }
            break;
        case 'createWall':
            // TODO: fix this on the Java side (send a hex string instead of a signed integer)
            var colorValue = (data.color > 0) ? data.color : 4294967296 + data.color;
            if (walls[data.wallId] != null) {
                walls[data.wallId].remove();
            }
            walls[data.wallId] = new google.maps.Polyline({
                path : [],
                strokeColor : '#' + colorValue.toString(16),
                strokeOpacity : 1.0,
                strokeWeight : 15,
                map : map
            });
            break;
        case 'updateWall':
            // Walls that were created before joining cannot be displayed
            if(walls.hasOwnProperty(data.wallId)) {
                walls[data.wallId].getPath().push(
                    new google.maps.LatLng(data.point.latitude, data.point.longitude)
                );
            }
            break;
        case 'removeWall':
            if (walls[data.wallId] != null)
                walls[data.wallId].remove();
            break;
        case 'ringBell':
            if(players.hasOwnProperty(data.playerId)) {
                players[data.playerId].setIcon(bikeBellIcon);
                setTimeout(function() { players[data.playerId].setIcon(bikeIcon); }, 3000);
            }
            break;
        case 'startGame':
            border = new google.maps.Circle({
                strokeColor: '#FF0000',
                strokeOpacity: 0.8,
                strokeWeight: 2,
                fillColor:'#000000',
                fillOpacity:0,
                map: map,
                center: {lat: data.startLocation.latitude, lng: data.startLocation.longitude},
                radius: data.borderSize
            });
            toastr.success("The game has started.");
            break;
        case 'winner':
            toastr.success("The game has ended.");
            break;
        case 'startEvent':
            switch (data.eventType) {
                case 'show_off_event':
                    toastr.success("Show off event started.");
                    break;
                case 'king_of_hill':
                    toastr.success("King of hill event started.");
                    break;
                case 'bell_event':
                    toastr.success("Bell event started.");
                    break;
            }
            break;
        case 'scoreMessage':
            toastr.success(
                "Player with id: "+data.playerId+" has won "
                 + data.score + " points in the last event."
            );
            break;
    }
}

function saveGame() {
    var gameData = new Blob([JSON.stringify(msgLog)], {type : 'text/plain'});
    window.open(URL.createObjectURL(gameData));
}

function setGame() {
    gameId = window.prompt('Game id?', '1');

    if(socket) {
        clearGame();
        socket.off();
    }

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
    if(paused || currentGame.i >= currentGame.data.length)
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
