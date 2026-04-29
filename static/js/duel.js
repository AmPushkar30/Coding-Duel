document.addEventListener("DOMContentLoaded", () => {
  const socket = io();

  const roomId = ROOM_ID;
  const playerName = PLAYER_NAME;

  // 🎨 Initialize Ace Editor
  const editor = ace.edit("editor");
  editor.setTheme("ace/theme/dracula");
  editor.session.setMode("ace/mode/python");
  editor.setOption("fontSize", "16px");
  editor.setOption("showPrintMargin", false);
  editor.setValue("# Write your code here...\n");
  window.editor = editor; // Make it global

  // Elements
  const timerEl = document.getElementById("timer");
  const submitBtn = document.getElementById("submitBtn");
  const p1PointsEl = document.getElementById("p1_points");
  const p2PointsEl = document.getElementById("p2_points");

  // 🕹️ Join Room
  socket.emit("join_room", { room_id: roomId, name: playerName });

  // 🕒 Shared Timer (starts when both players join)
  socket.on("start_timer", (data) => {
    let timeLeft = data.time || 600;
    const timer = setInterval(() => {
      if (timeLeft <= 0) {
        clearInterval(timer);
        submitBtn.disabled = true;
        socket.emit("time_up", { room_id: roomId });
        timerEl.textContent = "⏰ 00:00";
        return;
      }

      let minutes = Math.floor(timeLeft / 60);
      let seconds = timeLeft % 60;
      timerEl.textContent = `${minutes}:${seconds.toString().padStart(2, "0")}`;
      timeLeft--;
    }, 1000);
  });

  // 🧠 Code Submission
  submitBtn.addEventListener("click", () => {
    const code = editor.getValue().trim();
    if (!code) {
      showModal("✏️ Please write some code first!");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Submitting...";

    socket.emit("submit_code", {
      room_id: roomId,
      name: playerName,
      code,
    });
  });

  // 🧹 Clear Code
  document.getElementById("clearBtn").addEventListener("click", () => {
    editor.setValue("# Write your code here...\n");
  });

  // 🟢 Verdict & Output
  socket.on("verdict", (data) => {
    const { verdict } = data;
    showModal(verdict === "Accepted" ? "✅ Correct Answer!" : "❌ Wrong Answer!");
    submitBtn.disabled = false;
    submitBtn.textContent = "Submit Code";
  });

  // 🟡 Update Live Scores
  socket.on("update_scores", (data) => {
    const updatePoints = (el, newPoints) => {
      const oldPoints = parseInt(el.textContent);
      el.textContent = newPoints;
      el.style.color =
        newPoints > oldPoints
          ? "#00ff88"
          : newPoints < oldPoints
          ? "#ff5555"
          : "#ffffff";
      setTimeout(() => (el.style.color = "#ffffff"), 800);
    };

    updatePoints(p1PointsEl, data.player1_points);
    updatePoints(p2PointsEl, data.player2_points);
  });

  // 🧩 Load next question after submission
  socket.on("next_question", (data) => {
    const questionBox = document.getElementById("question-text");
    questionBox.style.opacity = 0;
    setTimeout(() => {
      questionBox.innerText = data.question;
      questionBox.style.opacity = 1;
    }, 300);
    editor.setValue("# Write your code here...\n");
  });

  // 🕐 Waiting for opponent
  socket.on("waiting_for_opponent", (data) => {
    showModal(data.message || "Waiting for your opponent to finish...");
  });

  // 🏁 Final result
  socket.on("duel_result", (data) => {
    const winner = data.winner;
    showFinalModal(`🏁 Match Ended! Winner: ${winner}`);
    submitBtn.disabled = true;
  });

  // ⚠️ Handle Errors
  socket.on("error", (data) => {
    showModal("⚠️ " + (data.message || "An error occurred"));
    submitBtn.disabled = false;
    submitBtn.textContent = "Submit Code";
  });
});

// ✅ Center Modal for verdicts
function showModal(message) {
  const modal = document.getElementById('resultModal');
  const msg = document.getElementById('modalMessage');
  msg.textContent = message;
  modal.classList.remove('hidden');

  document.getElementById('modalOkBtn').onclick = () => {
    modal.classList.add('hidden');
  };
}

function showFinalModal(message) {
  const modal = document.getElementById('finalModal');
  const msg = document.getElementById('finalMessage');
  msg.textContent = message;
  modal.classList.remove('hidden');

  document.getElementById('goHomeBtn').onclick = () => {
    window.location.href = '/index';
  };
}
