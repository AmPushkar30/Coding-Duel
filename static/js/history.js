document.querySelectorAll('.match-card').forEach(card => {
  card.addEventListener('click', () => {
    const matchId = card.dataset.id;
    window.location.href = `/match/${matchId}`;
  });
});
