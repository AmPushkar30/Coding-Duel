const menuIcon = document.querySelector('.menu-icon');
const sideMenu = document.getElementById('side-menu');
const closeMenu = document.getElementById('close-menu');

menuIcon.addEventListener('click', () => {
  sideMenu.classList.toggle('hidden');
});

closeMenu.addEventListener('click', () => {
  sideMenu.classList.add('hidden');
});

// Close menu when clicking outside
window.addEventListener('click', function (e) {
  if (!sideMenu.contains(e.target) && !menuIcon.contains(e.target)) {
    sideMenu.classList.add('hidden');
  }
});

// Glitch effect every 10 seconds
const headerText = document.querySelector('header h1');

setInterval(() => {
  headerText.classList.add('glitching');
  setTimeout(() => headerText.classList.remove('glitching'), 700);
}, 10000);


// Page redirect
document.querySelector('.grid-button:nth-child(1)').addEventListener('click', () => {
  window.location.href = '/leaderboard';
});

document.querySelector('.grid-button:nth-child(2)').addEventListener('click', () => {
  window.location.href = '/tutorials';
});

document.querySelector('.learn-button').addEventListener('click', () => {
  window.location.href = '/learn';
});

document.addEventListener('DOMContentLoaded', () => {
  const startButton = document.querySelector('.main-button');
  if (startButton) {
    startButton.addEventListener('click', () => {
      const startUrl = startButton.getAttribute('data-start-url');
      window.location.href = startUrl;
    });
  }
});

// Page loader
  window.addEventListener("load", () => {
    const loader = document.getElementById("page-loader");
    if (loader) {
      setTimeout(() => {
        loader.classList.add("hidden");
      }, 600);
    }
  });
