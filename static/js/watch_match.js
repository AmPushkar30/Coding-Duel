const socket = io();
const roomId = ROOM_ID;

socket.emit("admin_join_room", { room: roomId });

socket.on("update_scores", function(data) {
    document.getElementById("p1_points").innerText = data.player1_points;
    document.getElementById("p2_points").innerText = data.player2_points;
});

socket.on("code_update", function(data) {
    if (data.player === PLAYER1) {
        document.getElementById("player1_code").innerText = data.code;
    }
    if (data.player === PLAYER2) {
        document.getElementById("player2_code").innerText = data.code;
    }
});

socket.on("admin_alert", function(data) {
    const alertBox = document.getElementById("alerts");
    const div = document.createElement("div");
    div.innerHTML = `⚠ ${data.player}: ${data.reason}`;
    alertBox.prepend(div);
});

socket.on("verdict", function(data) {
    const log = document.getElementById("submission_log");
    const entry = document.createElement("div");
    entry.innerHTML = `📝 Submission: ${data.verdict}`;
    log.prepend(entry);
});

socket.on("start_timer", function(data) {
    let timeLeft = data.time;

    const timerEl = document.getElementById("live_timer");

    const timer = setInterval(() => {
        if (timeLeft <= 0) {
            clearInterval(timer);
            return;
        }
        let minutes = Math.floor(timeLeft / 60);
        let seconds = timeLeft % 60;
        timerEl.textContent = `${minutes}:${seconds.toString().padStart(2, "0")}`;
        timeLeft--;
    }, 1000);
});
