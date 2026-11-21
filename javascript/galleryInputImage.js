// Fill the ForgeCanvases taking gallery inputs through the gallery of diffus-app, as Create/Edit Image
// does: picked with the image selector, uploaded when dropped or pasted, loaded by reference when sent
// or run from the gallery. See modules/gallery_input_images.py.

// The selection in progress of each canvas, until its image is loaded.
const _gallerySelections = {};

// The load of each canvas sent to the server ({ref, selection}) and the one queued after it: one at a
// time, so an answer is that of the load sent; a load queued is replaced by a later one.
const _galleryLoads = {};

// What a Send to with no image answers (see send_image_from_url of infotext_utils.py).
const _GALLERY_NOTHING_SENT = "nothing";

// The img2img canvases by the label of their input, in the order of the img2img modes.
const _IMG2IMG_GALLERY_INPUTS = [
    ["img2img", "img2img_image"],
    ["sketch", "img2img_sketch"],
    ["inpaint", "img2maskimg"],
    ["inpaint sketch", "inpaint_sketch"],
];

// Null when WebUI is not embedded in diffus-app, its own uploads then used.
function _getInputImageApp() {
    try {
        return window.parent.diffusApp?.inputImage ?? null;
    } catch (error) {
        return null;
    }
}

function _isGalleryInputCanvas(uuid) {
    return !!gradioApp().getElementById(`${uuid}_gallery_load`);
}

function _getGalleryInputCanvasOf(element) {
    const container = element instanceof Element ? element.closest('[id^="container_"]') : null;
    const uuid = container?.id.slice("container_".length);
    return uuid && _isGalleryInputCanvas(uuid) ? uuid : null;
}

function _getGalleryRefTextarea(uuid) {
    return gradioApp().querySelector(`#${CSS.escape(`${uuid}_gallery_ref`)} textarea`);
}

function _getBackgroundTextarea(uuid) {
    return gradioApp().querySelector(`#${CSS.escape(uuid)}.logical_image_background textarea`);
}

function _getForegroundTextarea(uuid) {
    return gradioApp().querySelector(`#${CSS.escape(uuid)}.logical_image_foreground textarea`);
}

// The layer ForgeCanvas draws the strokes on, of the size of its image.
function _getDrawingCanvas(uuid) {
    return gradioApp().getElementById(`drawingCanvas_${uuid}`);
}

function _getGalleryInputLoading(uuid) {
    const container = gradioApp().getElementById(`container_${uuid}`);
    if (!container) {
        return null;
    }

    let overlay = container.querySelector(":scope > .gallery-input-loading");
    if (overlay) {
        return overlay;
    }

    overlay = document.createElement("div");
    overlay.className = "gallery-input-loading";
    overlay.innerHTML = `
        <div class="gallery-input-loading-progress"><span></span></div>
        <button type="button" class="gallery-input-loading-cancel" title="Cancel">✕</button>
    `;

    // An image dropped on the canvas meanwhile would be replaced by the one loading.
    for (const type of ["dragenter", "dragover", "drop"]) {
        overlay.addEventListener(type, (event) => {
            event.preventDefault();
            event.stopPropagation();
        });
    }

    overlay.querySelector(".gallery-input-loading-cancel").addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        _cancelGalleryInputImage(uuid);
    });

    container.appendChild(overlay);
    return overlay;
}

// A null progress shows an indeterminate one.
function _showGalleryInputLoading(uuid, progress) {
    const overlay = _getGalleryInputLoading(uuid);
    if (!overlay) {
        return;
    }

    const percentage = progress?.percentage ?? null;
    const ring = overlay.querySelector(".gallery-input-loading-progress");
    ring.classList.toggle("indeterminate", percentage === null);
    ring.style.setProperty("--gallery-input-progress", `${percentage ?? 0}%`);
    ring.querySelector("span").textContent = progress?.paused ? "Paused" : percentage === null ? "" : `${Math.round(percentage)}%`;

    overlay.classList.add("visible");
}

function _hideGalleryInputLoading(uuid) {
    const container = gradioApp().getElementById(`container_${uuid}`);
    container?.querySelector(":scope > .gallery-input-loading")?.classList.remove("visible");
}

function _isGalleryInputLoading(uuid) {
    return !!_gallerySelections[uuid];
}

// A selection cancelled or done: its image, picked or uploaded meanwhile, is not loaded.
function _cancelGalleryInputImage(uuid) {
    delete _gallerySelections[uuid];
    _hideGalleryInputLoading(uuid);
}

// Shown loading until galleryInputImageLoaded().
function _loadGalleryInputImage(uuid, ref, selection) {
    _showGalleryInputLoading(uuid, null);

    const loads = (_galleryLoads[uuid] ||= {sent: null, queued: null});
    if (loads.sent) {
        loads.queued = {ref, selection};
    } else {
        _sendGalleryLoad(uuid, {ref, selection});
    }
}

function _sendGalleryLoad(uuid, load) {
    _galleryLoads[uuid].sent = load;
    gradioApp().getElementById(`${uuid}_gallery_load`).click();
}

function _startGallerySelection(uuid) {
    _cancelGalleryInputImage(uuid);

    const selection = {};
    _gallerySelections[uuid] = selection;
    return selection;
}

// Pick an image by the image selector or an upload of diffus-app, which take the same options.
async function _pickGalleryInputImage(uuid, pick) {
    const selection = _startGallerySelection(uuid);

    let ref = null;
    try {
        ref = await pick({
            onUploadProgress: (progress) => {
                if (_gallerySelections[uuid] === selection) {
                    _showGalleryInputLoading(uuid, progress);
                }
            },
        });
    } catch (error) {
        console.error("Failed to pick the gallery input image", error);
    }

    // Cancelled, or taken over by another selection for the canvas.
    if (_gallerySelections[uuid] !== selection) {
        return;
    }

    if (!ref) {
        _cancelGalleryInputImage(uuid);
        return;
    }

    _loadGalleryInputImage(uuid, ref, selection);
}

// Load the input image of a run from the gallery. Its strokes are cleared: an input drawn over is not
// registered, while ForgeCanvas keeps them for an image of the same size.
function _setGalleryInputImage(uuid, ref) {
    const selection = _startGallerySelection(uuid);
    selection.clearsForeground = true;
    _loadGalleryInputImage(uuid, ref, selection);
}

// The reference the hidden load button sends to the server.
function takeGalleryInputImage(uuid) {
    const load = _galleryLoads[uuid]?.sent;
    return load ? JSON.stringify(load.ref) : "";
}

// Run once the hidden load button is done, with the background and reference loaded as JSON (empty when
// it failed): put into the canvas only if its selection is still in progress. Then sends the load
// queued, if still wanted. Clears the loaded value.
function galleryInputImageLoaded(uuid, loaded) {
    const loads = _galleryLoads[uuid];
    const selection = loads?.sent?.selection;
    const queued = loads?.queued;
    if (loads) {
        loads.sent = null;
        loads.queued = null;
    }

    if (selection && _gallerySelections[uuid] === selection) {
        _cancelGalleryInputImage(uuid);
        if (loaded) {
            const {background, ref} = JSON.parse(loaded);
            _putGalleryInputImage(uuid, background, ref, selection.clearsForeground);
        }
    }

    if (queued && _gallerySelections[uuid] === queued.selection) {
        _sendGalleryLoad(uuid, queued);
    }
    return "";
}

// Start sending an image to the canvas (Send to): a selection taking over the one in progress.
function startGalleryInputImageSend(uuid) {
    _startGallerySelection(uuid).isSend = true;
    _showGalleryInputLoading(uuid, null);
}

// Run once a send is done, with its background and reference as JSON (empty when it failed): put into
// the canvas as a load is, if the send is still in progress. Clears the sent value.
function galleryInputImageSent(uuid, sent) {
    // No send was started: one in progress from another button goes on.
    if (sent === _GALLERY_NOTHING_SENT) {
        return "";
    }

    if (_gallerySelections[uuid]?.isSend) {
        _cancelGalleryInputImage(uuid);
        if (sent) {
            const {background, ref} = JSON.parse(sent);
            _putGalleryInputImage(uuid, background, ref);
        }
    }
    return "";
}

function _putGalleryInputImage(uuid, background, ref, clearForeground = false) {
    const backgroundTextarea = _getBackgroundTextarea(uuid);
    const refTextarea = _getGalleryRefTextarea(uuid);
    if (!backgroundTextarea || !refTextarea) {
        return;
    }

    // No foreground, or an image of another size, whose strokes ForgeCanvas drops once it decodes it: a
    // blank one sent at its size now, as the sketch modes composite both.
    const size = _getPngSize(background);
    if (clearForeground || !_getForegroundTextarea(uuid)?.value || !_hasSize(_getDrawingCanvas(uuid), size)) {
        _clearForeground(uuid, size);
    }
    backgroundTextarea.value = background;
    updateInput(backgroundTextarea);
    refTextarea.value = ref;
    updateInput(refTextarea);
}

// The strokes of a canvas cleared at once, its drawing layer of the given size, and its foreground sent
// as that blank layer: ForgeCanvas polls its fields, saving its drawing layer once a new background is
// decoded, which may come first.
function _clearForeground(uuid, size) {
    const foregroundTextarea = _getForegroundTextarea(uuid);
    if (!foregroundTextarea) {
        return;
    }

    const drawing = _getDrawingCanvas(uuid);
    if (!_hasSize(drawing, size)) {
        // Resizing clears it.
        drawing.width = size.width;
        drawing.height = size.height;
    } else {
        drawing?.getContext("2d").clearRect(0, 0, drawing.width, drawing.height);
    }
    foregroundTextarea.value = drawing ? drawing.toDataURL() : "";
    updateInput(foregroundTextarea);
}

// Whether a canvas is of the size, or either is unknown.
function _hasSize(canvas, size) {
    return !canvas || !size || (canvas.width === size.width && canvas.height === size.height);
}

const _PNG_DATA_URL_PREFIX = "data:image/png;base64,";

// The size of a PNG data URL, as the server sends the backgrounds (image_to_base64 of canvas.py), read from
// its IHDR chunk; null for another image.
function _getPngSize(dataUrl) {
    if (!dataUrl.startsWith(_PNG_DATA_URL_PREFIX)) {
        return null;
    }

    try {
        // The signature, then the IHDR chunk: its length, type, width and height, 24 bytes.
        const header = atob(dataUrl.slice(_PNG_DATA_URL_PREFIX.length, _PNG_DATA_URL_PREFIX.length + 32));
        if (header.length < 24 || header.slice(12, 16) !== "IHDR") {
            return null;
        }
        const read = (offset) => [0, 1, 2, 3].reduce((value, i) => value * 256 + header.charCodeAt(offset + i), 0);
        return {width: read(16), height: read(20)};
    } catch (error) {
        return null;
    }
}

// The img2img mode of an input label, or -1.
function _getImg2imgMode(label) {
    return _IMG2IMG_GALLERY_INPUTS.findIndex(([inputLabel]) => inputLabel === label);
}

// The img2img mode of the input images of a run from the gallery, if any, switched to by its paste.
function getGalleryInputImg2imgMode(inputImages) {
    const mode = (inputImages || []).map(({label}) => _getImg2imgMode(label)).find((index) => index >= 0);
    return mode ?? null;
}

// Load the input images of a run from the gallery by their labels: the img2img ones into the canvas of
// their mode.
function loadGalleryInputImages(tabname, inputImages) {
    for (const {label, ...ref} of inputImages || []) {
        const img2imgMode = _getImg2imgMode(label);

        let uuid = null;
        if (tabname === "img2img" && img2imgMode >= 0) {
            uuid = _IMG2IMG_GALLERY_INPUTS[img2imgMode][1];
        }

        if (!uuid || !_isGalleryInputCanvas(uuid)) {
            console.warn(`No canvas for the gallery input image "${label}" in ${tabname}`);
        } else {
            _setGalleryInputImage(uuid, ref);
        }
    }
}

function _getImageFile(dataTransfer) {
    return Array.from(dataTransfer?.files || []).find((file) => file.type.startsWith("image/")) || null;
}

// Upload an image dropped or pasted on a canvas to the gallery, before the canvas sees it.
function _uploadGalleryInputImage(event, uuid, file) {
    if (!uuid || !file) {
        return;
    }

    const inputImageApp = _getInputImageApp();
    if (!inputImageApp) {
        return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();
    if (!_isGalleryInputLoading(uuid)) {
        _pickGalleryInputImage(uuid, (options) => inputImageApp.upload(file, options));
    }
}

// Every way a canvas opens the file chooser clicks its file input.
document.addEventListener("click", (event) => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.id.startsWith("imageInput_")) {
        return;
    }

    const uuid = input.id.slice("imageInput_".length);
    if (!_isGalleryInputCanvas(uuid)) {
        return;
    }

    const inputImageApp = _getInputImageApp();
    if (!inputImageApp) {
        return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();
    _pickGalleryInputImage(uuid, (options) => inputImageApp.select({...options, selectorKey: "webui"}));
}, true);

window.addEventListener("drop", (event) => {
    _uploadGalleryInputImage(event, _getGalleryInputCanvasOf(event.target), _getImageFile(event.dataTransfer));
}, true);

// A canvas takes a pasted image while the pointer is over it.
let _galleryInputPointer = null;

window.addEventListener("pointermove", (event) => {
    _galleryInputPointer = {x: event.clientX, y: event.clientY};
}, {capture: true, passive: true});

window.addEventListener("paste", (event) => {
    if (!_galleryInputPointer) {
        return;
    }

    const element = document.elementFromPoint(_galleryInputPointer.x, _galleryInputPointer.y);
    _uploadGalleryInputImage(event, _getGalleryInputCanvasOf(element), _getImageFile(event.clipboardData));
}, true);
