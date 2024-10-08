async function listFavoriteCheckpoints() {
    const params = new URLSearchParams({ is_favorite: true, type: "CHECKPOINT", sort: "NAME" });
    const url = `/gallery-api/v1/models?${params.toString()}`;

    const response = await fetchGet(url);
    if (!response.ok) {
        throw `Get favorite checkpoints failed: ${response.statusText}`;
    }
    const content = await response.json();

    return content.items;
}

async function updateCheckpointDropdown() {
    const checkpoints = await listFavoriteCheckpoints();

    return {
        choices: checkpoints.map((item) => `${item.filename} [${item.sha256.slice(0, 10)}]`),
        __type__: "update",
    };
}

async function updateCheckpointDropdownWithHR() {
    const checkpoints_update = await updateCheckpointDropdown();
    checkpoints_update.value = checkpoints_update.choices[0];

    const value = "Use same checkpoint";
    const hr_checkpoints_update = {
        value: value,
        choices: [value, ...checkpoints_update.choices],
        __type__: "update",
    };

    return [checkpoints_update, hr_checkpoints_update];
}

let _checkpoint_name = "";

function updateCheckpoint() {
    return {
        value: _checkpoint_name,
        __type__: "update",
    };
}

function _getStem(filename) {
    const index = filename.lastIndexOf(".");

    if (index === -1 || index === 0 || index === filename.length - 1) {
        return filename;
    }

    return filename.slice(0, index);
}

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

var galleryApp;

function initGallery() {
    const galleryDiv = document.querySelector("#gallery");
    if (!galleryDiv) {
        return;
    }
    const content = document.createElement("div");
    content.style = "width: 100%;";
    content.innerHTML = `
        <v-btn @click="openGallery">
            Model Gallery
        </v-btn>
        <v-dialog v-model="galleryOpen" overlay-color="white">
            <v-sheet width="100%" height="100%" rounded="lg" overflow-hidden>
                <iframe
                    src="gallery/"
                    id="gallery-iframe"
                    width="100%"
                    height="100%"
                    loading="eager"
                />
            </v-sheet>
        </v-dialog>
    `;
    galleryDiv.appendChild(content);

    const style = document.createElement("style");
    style.innerHTML = `
        .v-dialog {
            width: 85%;
            height: 85%;
        }
    `;
    document.head.appendChild(style);

    galleryApp = new Vue({
        el: "#gallery",
        vuetify: new Vuetify({
            theme: { dark: true },
        }),
        data() {
            return {
                galleryOpen: false,
            };
        },
        methods: {
            openGallery() {
                this.galleryOpen = true;
            },
            setCheckpoint(name) {
                _checkpoint_name = name;
                gradioApp().getElementById("gallery_change_checkpoint").click();
            },
            setExtraNetwork(model_type, filename) {
                let text;
                const stem = _getStem(filename);

                const tabname = get_uiCurrentTab().textContent.trim();
                if (!["txt2img", "img2img"].includes(tabname)) {
                    return null;
                }

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

                return {
                    tabname: tabname,
                    added: added,
                    text: text,
                };
            },
        },
    });
}

onUiLoaded(initGallery);
