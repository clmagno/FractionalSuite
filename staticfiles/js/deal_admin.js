// staticfiles/js/deal_admin.js

// We wait for the admin's built-in JS to load
window.addEventListener("load", function() {
    // Use 'grp' prefix for inlines, 'id_' for main forms
    const targetAmountField = document.getElementById("id_target_raise_amount");
    const totalSharesField = document.getElementById("id_total_shares_offered");

    if (!targetAmountField || !totalSharesField) {
        return; // Not on the right page
    }

    // Find the 'read-only' field we added
    const priceFieldWrapper = document.querySelector(".field-price_per_share .readonly");

    if (!priceFieldWrapper) {
        return;
    }

    // This is our new display
    priceFieldWrapper.innerHTML = `<strong id="calculated-price" style="font-size: 1.2em;">₱0.00</strong>`;
    const priceDisplay = document.getElementById("calculated-price");

    function calculatePrice() {
        const target = parseFloat(targetAmountField.value) || 0;
        const shares = parseInt(totalSharesField.value) || 0;

        if (shares > 0 && target > 0) {
            const price = (target / shares).toFixed(2);
            priceDisplay.textContent = `₱${price}`;
        } else {
            priceDisplay.textContent = "₱0.00";
        }
    }

    // Add listeners
    targetAmountField.addEventListener("input", calculatePrice);
    totalSharesField.addEventListener("input", calculatePrice);

    // Run once on page load
    calculatePrice();
});