let gallery_run_pnginfo = null;
let gallery_run_models = null;

const _TAB_ID_TO_NAME = {
    tab_txt2img: "txt2img",
    tab_img2img: "img2img",
};

function _updateExtraNetwork(tabname, text) {
    const textarea = gradioApp().querySelector(`#${tabname}_prompt > label > textarea`);
    let added;

    if (!tryToRemoveExtraNetworkFromPrompt(textarea, text)) {
        textarea.value = textarea.value + opts.extra_networks_add_text_separator + text;
        added = true;
    } else {
        added = false;
    }

    updateInput(textarea);
    return added;
}

const webUIApp = {
    updateFavoriteCheckpoints() {
        const refreshButton = gradioApp().getElementById("refresh_sd_model_checkpoint_dropdown");
        if (refreshButton) {
            refreshButton.click();
        }
    },
    setExtraNetwork(model_type, filename) {
        const toast = getDiffusApp().toast;

        let tab_id = get_uiCurrentTabContent().id.trim();
        if (!["tab_txt2img", "tab_img2img"].includes(tab_id)) {
            tab_id = "tab_txt2img";
            switchToTab(tab_id);
        }

        const tabname = _TAB_ID_TO_NAME[tab_id];

        let text;
        const stem = getStem(filename);

        switch (model_type) {
            case "LORA":
                text = `<lora:${stem}:1>`;
                break;
            case "LYCORIS":
                text = `<lyco:${stem}:1>`;
                break;
            case "EMBEDDING":
                text = stem;
                break;
            case "HYPERNETWORK":
                text = `<hypernet:${stem}:1>`;
                break;
            default:
                throw `Unknown Model Type: ${model_type}`;
        }
        const added = _updateExtraNetwork(tabname, text);
        const subject = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");

        toast.setExtraNetwork(added, tabname, subject);
    },
    runImage(tabname, pnginfo, models) {
        gallery_run_pnginfo = pnginfo;
        gallery_run_models = models;
        gradioApp().getElementById(`${tabname}_paste`).click();
    },
};

onUiLoaded(() => {
    window.webUIApp = webUIApp;
});
