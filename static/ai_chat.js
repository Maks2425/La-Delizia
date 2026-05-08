function initGlobalAiChat() {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
    const toggleBtn = document.getElementById("aiChatToggle");
    const closeBtn = document.getElementById("aiChatClose");
    const panel = document.getElementById("aiChatPanel");
    const form = document.getElementById("aiChatForm");
    const input = document.getElementById("aiChatInput");
    const messages = document.getElementById("aiChatMessages");

    if (!toggleBtn || !panel || !form || !input || !messages) {
        return;
    }

    function appendMessage(text, role) {
        const item = document.createElement("div");
        item.className = `ai-msg ${role === "user" ? "ai-msg-user" : "ai-msg-bot"}`;
        item.textContent = text;
        messages.appendChild(item);
        messages.scrollTop = messages.scrollHeight;
    }

    toggleBtn.addEventListener("click", () => {
        panel.classList.toggle("open");
        panel.setAttribute("aria-hidden", panel.classList.contains("open") ? "false" : "true");
        if (panel.classList.contains("open")) {
            input.focus();
        }
    });

    if (closeBtn) {
        closeBtn.addEventListener("click", () => {
            panel.classList.remove("open");
            panel.setAttribute("aria-hidden", "true");
        });
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const question = input.value.trim();
        if (!question) {
            return;
        }

        appendMessage(question, "user");
        input.value = "";

        try {
            const response = await fetch("/api/assistant/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken,
                },
                body: JSON.stringify({ message: question }),
            });
            const data = await response.json();
            if (!response.ok) {
                appendMessage(data.error || "Не вдалося отримати відповідь.", "bot");
                return;
            }
            appendMessage(data.reply || "Вибачте, я не зміг сформувати відповідь.", "bot");
        } catch (_error) {
            appendMessage("Помилка з'єднання. Спробуйте ще раз.", "bot");
        }
    });
}

initGlobalAiChat();
