const socket = io();

const playerName = document.getElementById('playerName').textContent.trim();
const playerEmail = document.getElementById('playerEmail').textContent.trim();
const statusText = document.getElementById('statusText');
const findBtn = document.getElementById('findBtn');
const cancelBtn = document.getElementById('cancelBtn');
const loader = document.getElementById('loader');
const languageSelect = document.getElementById('languageSelect');

let searching = false;

findBtn.addEventListener('click', () => {
  const language = document.getElementById('language').value;
  if (!language || searching) return;

  searching = true;
  statusText.textContent = `Finding an opponent (Language: ${language})...`;
  
  // UI transition
  loader.style.display = 'block';
  languageSelect.style.display = 'none';
  cancelBtn.style.display = 'inline-block';

  socket.emit('join_queue', { name: playerName, email: playerEmail, language });
});

cancelBtn.addEventListener('click', () => {
  if (!searching) return;
  searching = false;

  socket.emit('leave_queue', { email: playerEmail });
  statusText.textContent = "Matchmaking cancelled.";
  loader.style.display = 'none';
  cancelBtn.style.display = 'none';
  languageSelect.style.display = 'block';
});

socket.on('waiting', (data) => {
  statusText.textContent = data.message || 'Waiting for an opponent...';
});

socket.on('match_found', (data) => {
  statusText.textContent = '';
  statusText.classList.remove('status-anim');
  loader.style.display = 'none';
  cancelBtn.style.display = 'none';

  // Show overlay with pop-up
  const overlay = document.getElementById('matchOverlay');
  const message = document.getElementById('matchMessage');
  message.textContent = `🎯 Opponent found: ${data.opponent}`;
  overlay.classList.add('show');

  // Fade out + redirect after animation
  setTimeout(() => {
    overlay.style.opacity = '0';
  }, 1200);

  setTimeout(() => {
    window.location.href = `/duel?room_id=${data.room_id}`;
  }, 2000);
});


window.addEventListener('beforeunload', () => {
  socket.emit('leave_queue', { email: playerEmail });
});
