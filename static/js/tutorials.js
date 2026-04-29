const categoryFilter = document.getElementById("categoryFilter");
const difficultyFilter = document.getElementById("difficultyFilter");
const cards = document.querySelectorAll(".card");

function filterTutorials() {
  const selectedCategory = categoryFilter.value;
  const selectedDifficulty = difficultyFilter.value;

  cards.forEach(card => {
    const category = card.dataset.category;
    const difficulty = card.dataset.difficulty;

    const categoryMatch = selectedCategory === "all" || category === selectedCategory;
    const difficultyMatch = selectedDifficulty === "all" || difficulty === selectedDifficulty;

    card.style.display = categoryMatch && difficultyMatch ? "block" : "none";
  });
}

categoryFilter.addEventListener("change", filterTutorials);
difficultyFilter.addEventListener("change", filterTutorials);