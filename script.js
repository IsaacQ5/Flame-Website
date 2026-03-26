const downloadButtons = document.querySelectorAll(".download-button");
const statusText = document.getElementById("status");

downloadButtons.forEach((button) => {
    button.addEventListener("click", () => {
        statusText.textContent = `Downloading ${button.dataset.file}...`;
    });
});
