const webUIApp = {
    preset: {
        isLoaded: function () {
            return document.getElementById("forge_ui_preset") !== null;
        },
        listPresets: function () {
            const presets = document.getElementById("forge_ui_preset");
            let result = [];
            if (presets) {
                const labels = presets.querySelectorAll("label");
                result = Array.from(labels).map((label) => label.textContent.trim());
            }
            return result.length > 0 ? result : undefined;
        },
        setPreset: function (name) {
            const presets = document.getElementById("forge_ui_preset");
            if (presets) {
                const labels = presets.querySelectorAll("label");
                for (const label of labels) {
                    if (label.textContent.trim().toLowerCase() === name.trim().toLowerCase()) {
                        label.click();
                        break;
                    }
                }
            }
        },
    },
};

onUiLoaded(() => {
    window.webUIApp = webUIApp;
});
