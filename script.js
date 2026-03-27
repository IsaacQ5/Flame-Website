const downloadButtons = document.querySelectorAll(".download-button");
const statusText = document.getElementById("status");

downloadButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const fileName = button.dataset.file;
        const label = button.dataset.label;
        const size = button.dataset.size;

        statusText.textContent = `Starting ${fileName} (${size}) - ${label}.`;
    });
});
