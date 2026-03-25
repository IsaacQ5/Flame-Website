const downloadButton = document.getElementById("download-button");
const statusText = document.getElementById("status");

downloadButton.addEventListener("click", () => {
    statusText.textContent = "Downloading python-code.zip...";
});
