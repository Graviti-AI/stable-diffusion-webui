function extractNumberFromGenerateButton(str) {
    const matches = str.match(/\d+/);

    if (matches && matches.length > 0) {
        return parseInt(matches[0], 10); // Convert the string to an integer
    }

    return null;
}

function addGenerateGtagEvent(selector, itemName) {
    const creditsInfo = document.querySelector(selector);
    const credits = extractNumberFromGenerateButton(creditsInfo.textContent);
    if (credits) {
        gtag("event", "spend_virtual_currency", {
            value: credits,
            virtual_currency_name: "credits",
            item_name: itemName,
        });
    }
}
