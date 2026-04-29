const dishItems = document.querySelectorAll(".dish-item");
const previewImage = document.getElementById("previewImage");
const previewName = document.getElementById("previewName");
const previewDescription = document.getElementById("previewDescription");
const previewPrice = document.getElementById("previewPrice");
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
const isAuthenticated = document.body.dataset.userAuthenticated === "true";
const checkoutEndpoint = document.body.dataset.checkoutEndpoint || "/api/checkout";
const guestCartStorageKey = "ladelizia_guest_cart";
const cartToggle = document.getElementById("cartToggle");
const cartDrawer = document.getElementById("cartDrawer");
const cartItemsContainer = document.getElementById("cartItems");
const cartTotal = document.getElementById("cartTotal");
const cartCount = document.getElementById("cartCount");
const checkoutBtn = document.getElementById("checkoutBtn");

let cartItems = [];

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

function animateAdd(plusElement) {
    if (!cartToggle) {
        return;
    }

    const plusRect = plusElement.getBoundingClientRect();
    const cartRect = cartToggle.getBoundingClientRect();

    const flyToken = document.createElement("span");
    flyToken.className = "fly-plus-token";
    flyToken.textContent = "+";
    flyToken.style.left = `${plusRect.left + plusRect.width / 2}px`;
    flyToken.style.top = `${plusRect.top + plusRect.height / 2}px`;

    const deltaX = cartRect.left + cartRect.width / 2 - (plusRect.left + plusRect.width / 2);
    const deltaY = cartRect.top + cartRect.height / 2 - (plusRect.top + plusRect.height / 2);

    flyToken.style.setProperty("--fly-x", `${deltaX}px`);
    flyToken.style.setProperty("--fly-y", `${deltaY}px`);

    document.body.appendChild(flyToken);

    requestAnimationFrame(() => {
        flyToken.classList.add("fly-plus-token-active");
    });

    cartToggle.classList.remove("cart-toggle-hit");
    void cartToggle.offsetWidth;
    cartToggle.classList.add("cart-toggle-hit");

    setTimeout(() => {
        flyToken.remove();
        cartToggle.classList.remove("cart-toggle-hit");
    }, 1450);
}

function showAddToast(dishName) {
    const toast = document.createElement("div");
    toast.className = "cart-toast";
    toast.textContent = `Додано: ${dishName}`;
    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.add("cart-toast-visible");
    });

    setTimeout(() => {
        toast.classList.remove("cart-toast-visible");
        setTimeout(() => toast.remove(), 200);
    }, 1300);
}

function upsertCartItem(itemToAdd) {
    const existing = cartItems.find((item) => item.name === itemToAdd.name);
    if (existing) {
        existing.qty += 1;
        return;
    }
    cartItems.push({ ...itemToAdd, qty: 1 });
}

function decreaseCartItem(name) {
    const existing = cartItems.find((item) => item.name === name);
    if (!existing) {
        return;
    }
    existing.qty -= 1;
    if (existing.qty <= 0) {
        cartItems = cartItems.filter((item) => item.name !== name);
    }
}

function calculateTotal() {
    return cartItems.reduce((sum, item) => sum + Number(item.price) * Number(item.qty || 1), 0);
}

function renderCart() {
    if (!cartItemsContainer || !cartTotal || !cartCount) {
        return;
    }

    const totalQty = cartItems.reduce((sum, item) => sum + Number(item.qty || 1), 0);
    cartCount.textContent = String(totalQty);
    cartTotal.textContent = `${calculateTotal()} грн`;

    if (cartItems.length === 0) {
        cartItemsContainer.innerHTML = '<p class="cart-empty">Кошик порожній</p>';
        return;
    }

    cartItemsContainer.innerHTML = cartItems
        .map(
            (item) => `
            <div class="cart-row">
                <div class="cart-row-main">
                    <span>${item.name} x${item.qty}</span>
                    <strong>${Number(item.price) * Number(item.qty)} грн</strong>
                </div>
                <button class="cart-minus-btn" type="button" data-name="${item.name}" aria-label="Забрати одну страву">−</button>
            </div>
        `
        )
        .join("");
}

function getDishFromButton(button) {
    return {
        name: button.dataset.name || "",
        description: button.dataset.description || "",
        price: Number(button.dataset.price || 0),
        image: button.dataset.image || "",
    };
}

async function saveCart() {
    if (!isAuthenticated) {
        localStorage.setItem(guestCartStorageKey, JSON.stringify(cartItems));
        return;
    }

    try {
        await fetch("/api/cart", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },
            body: JSON.stringify({ items: cartItems }),
        });
    } catch (error) {
        console.error("Не вдалося зберегти кошик:", error);
    }
}

async function loadCart() {
    if (!isAuthenticated) {
        const raw = localStorage.getItem(guestCartStorageKey);
        try {
            cartItems = raw ? JSON.parse(raw) : [];
        } catch (_error) {
            cartItems = [];
        }
        return;
    }

    try {
        const response = await fetch("/api/cart");
        if (!response.ok) {
            cartItems = [];
            return;
        }
        const data = await response.json();
        cartItems = Array.isArray(data.items) ? data.items : [];
    } catch (error) {
        console.error("Не вдалося завантажити кошик:", error);
        cartItems = [];
    }
}

async function addDishToCart(button, plusElement) {
    const dish = getDishFromButton(button);
    if (!dish.name) {
        return;
    }

    upsertCartItem(dish);
    animateAdd(plusElement);
    showAddToast(dish.name);
    await saveCart();
    renderCart();
}

async function checkoutOrder() {
    if (cartItems.length === 0) {
        alert("Кошик порожній.");
        return;
    }

    if (!isAuthenticated) {
        window.location.href = "/login";
        return;
    }

    try {
        const response = await fetch(checkoutEndpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },
            body: JSON.stringify({ items: cartItems, total: calculateTotal() }),
        });
        const data = await response.json();
        if (!response.ok) {
            alert("Не вдалося оформити замовлення.");
            return;
        }

        cartItems = [];
        await saveCart();
        renderCart();
        alert("Замовлення оформлено!");
        if (data.redirect_url) {
            window.location.href = data.redirect_url;
        }
    } catch (error) {
        console.error("Помилка оформлення:", error);
        alert("Не вдалося оформити замовлення.");
    }
}

dishItems.forEach((item) => {
    item.addEventListener("click", async (event) => {
        setActiveDish(item);
        updatePreview(item);

        const plusElement = event.target.closest(".dish-plus");
        if (plusElement) {
            await addDishToCart(item, plusElement);
        }
    });
});

loadCart().then(renderCart);

if (cartToggle && cartDrawer) {
    cartToggle.addEventListener("click", () => {
        cartDrawer.classList.toggle("cart-drawer-open");
        cartDrawer.setAttribute("aria-hidden", cartDrawer.classList.contains("cart-drawer-open") ? "false" : "true");
    });
}

if (checkoutBtn) {
    checkoutBtn.addEventListener("click", checkoutOrder);
}

if (cartItemsContainer) {
    cartItemsContainer.addEventListener("click", async (event) => {
        const minusBtn = event.target.closest(".cart-minus-btn");
        if (!minusBtn) {
            return;
        }
        const dishName = minusBtn.dataset.name;
        if (!dishName) {
            return;
        }

        decreaseCartItem(dishName);
        await saveCart();
        renderCart();
    });
}
