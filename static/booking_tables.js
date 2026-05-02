const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
const confirmTableBtn = document.getElementById("confirmTableBtn");
const tableButtons = Array.from(document.querySelectorAll(".table-seat"));
const timeSelect = document.getElementById("timeSelect");
const timeSlotsHints = document.getElementById("timeSlotsHints");

let selectedTable = window.bookingInitialTable || null;
let selectedTime = window.bookingInitialTime || "17:00";
const reservedBySlot = window.bookingReservedBySlot || {};
const totalTables = tableButtons.length || 1;

function tableIsReserved(tableId, slot) {
    const reservedList = Array.isArray(reservedBySlot[slot]) ? reservedBySlot[slot] : [];
    return reservedList.includes(tableId);
}

function renderSelection() {
    tableButtons.forEach((button) => {
        const tableId = Number(button.dataset.tableId);
        const isReserved = tableIsReserved(tableId, selectedTime);
        button.setAttribute("aria-disabled", isReserved ? "true" : "false");
        button.classList.toggle("is-unavailable", isReserved);
        button.classList.toggle("is-reserved", isReserved);

        if (isReserved && selectedTable === tableId) {
            selectedTable = null;
        }
        const isSelected = tableId === selectedTable;
        button.classList.toggle("is-free", !isReserved && !isSelected);
        button.classList.toggle("is-selected", isSelected);
    });
    if (confirmTableBtn) {
        confirmTableBtn.disabled = !selectedTable;
    }
    renderTimeHints();
}

function getTimeSlotLoadClass(slot) {
    const reservedList = Array.isArray(reservedBySlot[slot]) ? reservedBySlot[slot] : [];
    const occupancyRatio = reservedList.length / totalTables;
    if (occupancyRatio >= 0.5) {
        return "is-busy";
    }
    if (occupancyRatio >= 0.25) {
        return "is-medium";
    }
    return "is-free";
}

function renderTimeHints() {
    if (!timeSlotsHints || !timeSelect) {
        return;
    }

    const options = Array.from(timeSelect.options);
    timeSlotsHints.innerHTML = options
        .map((option) => {
            const slot = option.value;
            const isActive = slot === selectedTime;
            const loadClass = getTimeSlotLoadClass(slot);
            const reservedCount = (reservedBySlot[slot] || []).length;
            return `
                <button
                    type="button"
                    class="time-slot-chip ${loadClass}${isActive ? " is-active" : ""}"
                    data-time-slot="${slot}"
                    title="Зайнято: ${reservedCount} з ${totalTables}"
                >
                    ${slot}
                </button>
            `;
        })
        .join("");
}

async function confirmSelectedTable() {
    if (!selectedTable) {
        return;
    }

    const response = await fetch("/api/booking/select-table", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({ table_id: selectedTable, time_slot: selectedTime }),
    });

    const data = await response.json();
    if (!response.ok) {
        alert(data.error || "Не вдалося забронювати столик");
        return;
    }

    window.location.href = data.redirect_url;
}

tableButtons.forEach((button) => {
    button.addEventListener("click", () => {
        if (button.classList.contains("is-unavailable")) {
            return;
        }
        selectedTable = Number(button.dataset.tableId);
        renderSelection();
    });
});

if (confirmTableBtn) {
    confirmTableBtn.addEventListener("click", confirmSelectedTable);
}

if (timeSelect) {
    timeSelect.addEventListener("change", () => {
        selectedTime = timeSelect.value;
        renderSelection();
    });
}

if (timeSlotsHints) {
    timeSlotsHints.addEventListener("click", (event) => {
        const chip = event.target.closest(".time-slot-chip");
        if (!chip || !timeSelect) {
            return;
        }
        selectedTime = chip.dataset.timeSlot || selectedTime;
        timeSelect.value = selectedTime;
        renderSelection();
    });
}

renderSelection();
