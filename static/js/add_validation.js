document.addEventListener("DOMContentLoaded", function () {

    const existingDepts = window.existingDepts || [];
    const prodInput = document.getElementById("prodnum");
    const deptSelect = document.getElementById("department_id");

    // WARNING BOX
    const warnBox = document.createElement("div");
    warnBox.style.color = "red";
    warnBox.style.marginTop = "8px";
    warnBox.style.display = "none";
    warnBox.innerHTML =
        "⚠ No matching department found for this product number. Please select manually.";
    deptSelect.parentNode.appendChild(warnBox);

    // VALIDATION LOGIC
    prodInput.addEventListener("input", function () {
        const value = prodInput.value.trim();
        const firstChar = value.charAt(0);

        // Reset
        if (!firstChar || isNaN(firstChar)) {
            deptSelect.value = "";
            warnBox.style.display = "none";
            return;
        }

        const digit = parseInt(firstChar);

        // Auto-select only for digits 1–9
        if (digit >= 1 && digit <= 9) {
            if (existingDepts.includes(digit)) {
                deptSelect.value = digit.toString();
                warnBox.style.display = "none";
            } else {
                deptSelect.value = "";
                warnBox.style.display = "block";
            }
        } else {
            deptSelect.value = "";
            warnBox.style.display = "none";
        }
    });
});
