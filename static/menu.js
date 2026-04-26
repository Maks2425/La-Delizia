const dishItems = document.querySelectorAll(".dish-item");
const previewImage = document.getElementById("previewImage");
const previewName = document.getElementById("previewName");
const previewDescription = document.getElementById("previewDescription");
const previewPrice = document.getElementById("previewPrice");

function setActiveDish(selectedItem) {
    dishItems.forEach((item) => item.classList.remove("active"));
    selectedItem.classList.add("active");
}

function updatePreview(selectedItem) {
    if (!previewImage || !previewName || !previewDescription || !previewPrice) {
        return;
    }

    previewImage.src = selectedItem.dataset.image || "";
    previewImage.alt = selectedItem.dataset.name || "Dish";
    previewName.textContent = selectedItem.dataset.name || "";
    previewDescription.textContent = selectedItem.dataset.description || "";
    previewPrice.textContent = `${selectedItem.dataset.price || "0"} грн`;
}

dishItems.forEach((item) => {
    item.addEventListener("click", () => {
        setActiveDish(item);
        updatePreview(item);
    });
});
