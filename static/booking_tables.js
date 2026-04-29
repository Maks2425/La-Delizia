const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
const confirmTableBtn = document.getElementById("confirmTableBtn");
const tableButtons = Array.from(document.querySelectorAll(".table-seat"));
const timeSelect = document.getElementById("timeSelect");

let selectedTable = window.bookingInitialTable || null;
let selectedTime = window.bookingInitialTime || "17:00";
const reservedBySlot = window.bookingReservedBySlot || {};

function tableIsReserved(tableId, slot) {
    const reservedList = Array.isArray(reservedBySlot[slot]) ? reservedBySlot[slot] : [];
    return reservedList.includes(tableId);
}

function renderSelection() {
    tableButtons.forEach((button) => {
        const tableId = Number(button.dataset.tableId);
        const isReserved = tableIsReserved(tableId, selectedTime);
        button.disabled = isReserved;
        button.classList.toggle("is-reserved", isReserved);

        if (isReserved && selectedTable === tableId) {
            selectedTable = null;
        }
        button.classList.toggle("is-selected", tableId === selectedTable);
    });
    if (confirmTableBtn) {
        confirmTableBtn.disabled = !selectedTable;
    }
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
        if (button.disabled) {
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

renderSelection();
