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

async function listFavoriteCheckpointTitles() {
    const checkpoints = await listFavoriteCheckpoints();
    return checkpoints.map((item) => `${item.filename} [${item.sha256.slice(0, 10)}]`);
}

async function updateCheckpointDropdown() {
    const titles = await listFavoriteCheckpointTitles();

    return { choices: titles, __type__: "update" };
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

function _XYZGridHelper(index, flag) {
    async function inner(...args) {
        args[index] = flag(args) ? await listFavoriteCheckpointTitles() : null;
        return args;
    }
    return inner;
}

const XYZGridHelpers = {
    select_axis: _XYZGridHelper(4, (args) =>
        ["Checkpoint name", "Refiner checkpoint"].includes(args[0]),
    ),
    fill: _XYZGridHelper(2, (args) => ["Checkpoint name", "Refiner checkpoint"].includes(args[0])),
    change_choice_mode: _XYZGridHelper(10, (args) =>
        [args[1], args[4], args[7]].some((type) =>
            ["Checkpoint name", "Refiner checkpoint"].includes(type),
        ),
    ),
};

let gallery_run_pnginfo = null;
let gallery_run_models = null;

let _checkpoint_name = null;

function updateCheckpoint() {
    return {
        value: _checkpoint_name,
        __type__: "update",
    };
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
    galleryDiv.setAttribute("data-app", "");

    const content = document.createElement("div");
    content.id = "gallery-inner";

    content.innerHTML = `
        <button id="introjs_button" class="mdi mdi-help-circle-outline" style="font-size: 1.4rem;"></button>

        <v-btn class="gallery-btn" large @click="openModelPage">
            <v-icon left> mdi-view-grid-outline </v-icon>
            Model Gallery
        </v-btn>
        <v-btn class="gallery-btn" large @click="openImagePage">
            <v-icon left> mdi-image-outline </v-icon>
            Image Gallery
        </v-btn>

        <v-dialog v-model="galleryOpen" width="100%" eager>
            <v-sheet width="100%" height="100%">
                <iframe
                    ref="iframe"
                    id="gallery-iframe"
                    src="gallery/"
                    width="100%"
                    height="100%"
                />
            </v-sheet>
        </v-dialog>
    `;
    galleryDiv.appendChild(content);

    const style = document.createElement("style");
    style.innerHTML = `
        #gallery {
            margin-left: auto;
            max-width: 100% !important;
        }
        #gallery-inner {
            width: 100%;
            display: flex;
            gap: 16px;
            align-items: center;
        }
        .gallery-btn {
            border-radius: 8px !important;
            background: var(--button-primary-background-fill) !important;
            font-weight: var(--button-large-text-weight) !important;
            font-size: var(--button-large-text-size) !important;
            color: var(--button-primary-text-color) !important;
            min-width: 25vw !important;
        }
        .v-dialog {
            height: 100%;
            overflow: hidden;
            border-radius: 8px;
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
            setCheckpoint(filename, sha256) {
                _checkpoint_name = `${filename} [${sha256.slice(0, 10)}]`;
                gradioApp().getElementById("gallery_change_checkpoint").click();
            },
            setExtraNetwork(model_type, filename) {
                const tabname = get_uiCurrentTab().textContent.trim();
                if (!["txt2img", "img2img"].includes(tabname)) {
                    return null;
                }

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

                return {
                    tabname: tabname,
                    added: added,
                    text: text,
                };
            },
            openModelPage() {
                const switchPage = this.$refs.iframe.contentWindow.switchModelPage;
                if (!switchPage) {
                    return;
                }
                switchPage();
                this.galleryOpen = true;
            },
            openImagePage() {
                const switchPage = this.$refs.iframe.contentWindow.switchImagePage;
                if (!switchPage) {
                    return;
                }
                switchPage();
                this.galleryOpen = true;
            },
            runTxt2Img(pnginfo, models) {
                gallery_run_pnginfo = pnginfo;
                gallery_run_models = models;
                gradioApp().getElementById("paste").click();
                this.galleryOpen = false;
            },
        },
    });
}

onUiLoaded(initGallery);
