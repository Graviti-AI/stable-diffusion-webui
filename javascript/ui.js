// various functions for interaction with ui.py not large enough to warrant putting them in separate files

function set_theme(theme) {
    const url = new URL(window.location.href);

    if (!url.searchParams.has("__theme")) {
        url.searchParams.set("__theme", theme);
        window.location.replace(url.toString());
    }
}

function all_gallery_buttons() {
    var allGalleryButtons = gradioApp().querySelectorAll('[style="display: block;"].tabitem div[id$=_gallery].gradio-gallery .thumbnails > .thumbnail-item.thumbnail-small');
    var visibleGalleryButtons = [];
    allGalleryButtons.forEach(function(elem) {
        if (elem.parentElement.offsetParent) {
            visibleGalleryButtons.push(elem);
        }
    });
    return visibleGalleryButtons;
}

function selected_gallery_button() {
    return all_gallery_buttons().find(elem => elem.classList.contains('selected')) ?? null;
}

function selected_gallery_index() {
    return all_gallery_buttons().findIndex(elem => elem.classList.contains('selected'));
}

function gallery_container_buttons(gallery_container) {
    return gradioApp().querySelectorAll(`#${gallery_container} .thumbnail-item.thumbnail-small`);
}

function selected_gallery_index_id(gallery_container) {
    return Array.from(gallery_container_buttons(gallery_container)).findIndex(elem => elem.classList.contains('selected'));
}

function extract_image_from_gallery(gallery) {
    if (gallery.length == 0) {
        return [null];
    }

    var index = selected_gallery_index();

    if (index < 0 || index >= gallery.length) {
        // Use the first image in the gallery as the default
        index = 0;
    }

    return [[gallery[index]]];
}

function extract_image_url_from_gallery_urls(gallery_urls) {
    if (gallery_send_to_url) {
        let result = [gallery_send_to_url];
        gallery_send_to_url = null;
        return result;
    }

    if (gallery_urls.length == 0) {
        return [null];
    }

    var index = selected_gallery_index();

    if (index < 0 || index >= gallery_urls.length) {
        // Use the first image in the gallery as the default
        index = 0;
    }

    return [gallery_urls[index]];
}

function update_gallery_urls(gallery) {
    return { value: gallery.map((item) => item.image.url), __type__: "update" }
}

window.args_to_array = Array.from; // Compatibility with e.g. extensions that may expect this to be around

function switchToTab(tab_id) {
    const tabItems = gradioApp().querySelectorAll('#tabs > .tabitem');
    const buttons = gradioApp().querySelectorAll("#tabs > div.tab-nav > button")
    buttons[Array.from(tabItems).findIndex(el => el.id === tab_id)].click();
}

function switch_to_txt2img() {
    switchToTab("tab_txt2img");
    return Array.from(arguments);
}

function switch_to_img2img_tab(no) {
    switchToTab("tab_img2img");
    gradioApp().getElementById('mode_img2img').querySelectorAll('button')[no].click();
}
function switch_to_img2img() {
    switch_to_img2img_tab(0);
    return Array.from(arguments);
}

function switch_to_sketch() {
    switch_to_img2img_tab(1);
    return Array.from(arguments);
}

function switch_to_inpaint() {
    switch_to_img2img_tab(2);
    return Array.from(arguments);
}

function switch_to_inpaint_sketch() {
    switch_to_img2img_tab(3);
    return Array.from(arguments);
}

function switch_to_extras() {
    switchToTab("tab_extras");

    return Array.from(arguments);
}

function get_tab_index(tabId) {
    let buttons = gradioApp().getElementById(tabId).querySelector('div').querySelectorAll('button');
    for (let i = 0; i < buttons.length; i++) {
        if (buttons[i].classList.contains('selected')) {
            return i;
        }
    }
    return 0;
}

function create_tab_index_args(tabId, args) {
    var res = Array.from(args);
    res[0] = get_tab_index(tabId);
    return res;
}

function get_img2img_tab_index() {
    let res = Array.from(arguments);
    res.splice(-2);
    res[0] = randomId();
    res[1] = get_tab_index('mode_img2img');
    return res;
}

function create_submit_args(args) {
    var res = Array.from(args);

    // As it is currently, txt2img and img2img send back the previous output args (txt2img_gallery, generation_info, html_info) whenever you generate a new image.
    // This can lead to uploading a huge gallery of previously generated images, which leads to an unnecessary delay between submitting and beginning to generate.
    // I don't know why gradio is sending outputs along with inputs, but we can prevent sending the image gallery here, which seems to be an issue for some.

    // If gradio at some point stops sending outputs, this may break something
    if (Array.isArray(res[res.length - 4])) {
        //res[res.length - 4] = null;
        // simply drop output args
        res = res.slice(0, res.length - 4);
    } else if (Array.isArray(res[res.length - 3])) {
        // for submit_extras()
        //res[res.length - 3] = null;
        res = res.slice(0, res.length - 3);
    }

    return res;
}

function setGenerationDisabled(tabname, disabled) {
    gradioApp().getElementById(tabname + '_generate').disabled = disabled;
}

function setSubmitButtonsVisibility(tabname, showInterrupt, showSkip, showInterrupting) {
    gradioApp().getElementById(tabname + '_interrupt').style.display = showInterrupt ? "block" : "none";
    gradioApp().getElementById(tabname + '_skip').style.display = showSkip ? "block" : "none";
    gradioApp().getElementById(tabname + '_interrupting').style.display = showInterrupting ? "block" : "none";
}

function showSubmitButtons(tabname, show) {
    setSubmitButtonsVisibility(tabname, !show, !show, false);
}

function showSubmitInterruptingPlaceholder(tabname) {
    setSubmitButtonsVisibility(tabname, false, true, true);
}

function showRestoreProgressButton(tabname, show) {
    return;
    var button = gradioApp().getElementById(tabname + "_restore_progress");
    if (!button) return;
    button.style.setProperty('display', show ? 'flex' : 'none', 'important');
}

const idToItemNames = {};

async function _submit() {
    var res = create_submit_args(arguments);
    const signature = getSignatureFromArgs(res);
    const index = signature.indexOf("model_title");
    res[index] = getDiffusCheckpointsApp().getTitle();

    const [all_style_info_index, all_style_info] = await getAllStyleInfo(res, signature);
    const [all_model_info_index, all_model_info] = await getAllModelInfo("txt2img", res, signature, all_style_info);

    tierCheckFlux(all_model_info);

    showSubmitButtons('txt2img', false);

    var id = randomId();
    localSet("txt2img_task_id", id);

    requestProgress(id, gradioApp().getElementById('txt2img_gallery_container'), gradioApp().getElementById('txt2img_gallery'), function() {
        showSubmitButtons('txt2img', true);
        localRemove("txt2img_task_id");
        showRestoreProgressButton('txt2img', false);
    });

    res[0] = id;
    res[all_style_info_index] = all_style_info === null ? null : JSON.stringify(all_style_info);
    res[all_model_info_index] = all_model_info === null ? null : JSON.stringify(all_model_info);

    return res;
}

async function submit_internal() {
    await tierCheckGenerate("txt2img", arguments);

    const res = await _submit(...arguments);

    const id = res[0];
    idToItemNames[id] = "txt2img_generation_button";

    return res
}

async function submit() {
    const tabname = "txt2img";
    setGenerationDisabled(tabname, true);
    try {
        return await submit_internal(...arguments);
    } finally {
        setGenerationDisabled(tabname, false);
    }
}

async function submit_txt2img_upscale() {
    var res = await _submit(...arguments);

    res[2] = selected_gallery_index();

    return res;
}

async function submit_img2img_internal() {
    await tierCheckGenerate("img2img", arguments);
    showSubmitButtons('img2img', false);

    var res = create_submit_args(arguments);
    const signature = getSignatureFromArgs(res);
    const index = signature.indexOf("model_title");
    res[index] = getDiffusCheckpointsApp().getTitle();

    const [all_style_info_index, all_style_info] = await getAllStyleInfo(res, signature);
    const [all_model_info_index, all_model_info] = await getAllModelInfo("img2img", res, signature, all_style_info);

    tierCheckFlux(all_model_info);

    var id = randomId();
    idToItemNames[id] = "img2img_generation_button";
    localSet("img2img_task_id", id);

    requestProgress(id, gradioApp().getElementById('img2img_gallery_container'), gradioApp().getElementById('img2img_gallery'), function() {
        showSubmitButtons('img2img', true);
        localRemove("img2img_task_id");
        showRestoreProgressButton('img2img', false);
    });


    res[0] = id;
    res[1] = get_tab_index('mode_img2img');
    res[all_style_info_index] = all_style_info === null ? null : JSON.stringify(all_style_info);
    res[all_model_info_index] = all_model_info === null ? null : JSON.stringify(all_model_info);

    return res;
}

async function submit_img2img() {
    const tabname = "img2img";
    setGenerationDisabled(tabname, true);
    try {
        return await submit_img2img_internal(...arguments);
    } finally {
        setGenerationDisabled(tabname, false);
    }
}

function submit_extras() {
    showSubmitButtons('extras', false);

    var id = randomId();
    localStorage.setItem("txt2img_task_id", id);

    requestProgress(id, gradioApp().getElementById('extras_gallery_container'), gradioApp().getElementById('extras_gallery'), function() {
        showSubmitButtons('extras', true);
    });

    var res = create_submit_args(arguments);

    res[0] = id;

    return res;
}

function submit_run_annotator() {
    const res = Array.from(arguments);
    res[0] = randomId();

    return res;
}

function updateExtraResults() {
    const inputs = Array.from(arguments);
    const all_results = JSON.parse(inputs[0]);
    const index = selected_gallery_index();

    const caption_result = all_results.captions[index];
    if (caption_result) {
        return [all_results.info + caption_result];
    }
    return all_results.info;
}

function restoreProgressTxt2img() {
    showRestoreProgressButton("txt2img", false);
    var id = localGet("txt2img_task_id");

    if (id) {
        showSubmitInterruptingPlaceholder('txt2img');
        requestProgress(id, gradioApp().getElementById('txt2img_gallery_container'), gradioApp().getElementById('txt2img_gallery'), function() {
            showSubmitButtons('txt2img', true);
        }, null, 0);
    }

    return id;
}

function restoreProgressImg2img() {
    showRestoreProgressButton("img2img", false);

    var id = localGet("img2img_task_id");

    if (id) {
        showSubmitInterruptingPlaceholder('img2img');
        requestProgress(id, gradioApp().getElementById('img2img_gallery_container'), gradioApp().getElementById('img2img_gallery'), function() {
            showSubmitButtons('img2img', true);
        }, null, 0);
    }

    return id;
}

function getImageGenerationTaskId(id_task, tabname){
    return [localStorage.getItem(`${tabname}_task_id`), tabname];
}

/**
 * Configure the width and height elements on `tabname` to accept
 * pasting of resolutions in the form of "width x height".
 */
function setupResolutionPasting(tabname) {
    var width = gradioApp().querySelector(`#${tabname}_width input[type=number]`);
    var height = gradioApp().querySelector(`#${tabname}_height input[type=number]`);
    for (const el of [width, height]) {
        el.addEventListener('paste', function(event) {
            var pasteData = event.clipboardData.getData('text/plain');
            var parsed = pasteData.match(/^\s*(\d+)\D+(\d+)\s*$/);
            if (parsed) {
                width.value = parsed[1];
                height.value = parsed[2];
                updateInput(width);
                updateInput(height);
                event.preventDefault();
            }
        });
    }
}

onUiLoaded(function() {
    showRestoreProgressButton('txt2img', localGet("txt2img_task_id"));
    showRestoreProgressButton('img2img', localGet("img2img_task_id"));
    setupResolutionPasting('txt2img');
    setupResolutionPasting('img2img');
});

onUiLoaded(function() {
    let gr_tabs = document.querySelector("#tabs");
    let tab_items = gr_tabs.querySelectorAll(":scope>.tabitem");
    let tab_buttons = gr_tabs.querySelector(".tab-nav").querySelectorAll(":scope>button");
    if (tab_items.length === tab_buttons.length) {
        tab_items.forEach(function(tab_item, index) {
            if (tab_item.classList.contains("hidden")) {
                tab_buttons[index].classList.add("hidden");
            }
        });
    }
});


function modelmerger() {
    var id = randomId();
    requestProgress(id, gradioApp().getElementById('modelmerger_results_panel'), null, function() {});

    var res = create_submit_args(arguments);
    res[0] = id;
    return res;
}

function debounceCalcuteTimes(func, type, wait=1000,immediate) {
    let timer = {};
    timer[type] = null;
    return function () {
        let context = this;
        let args = arguments;
        if (timer[type]) clearTimeout(timer[type]);
        if (immediate) {
            const callNow = !timer;
            timer[type] = setTimeout(() => {
                timer = null;
            }, wait)
            if (callNow) func.apply(context, args)
        } else {
            timer[type] = setTimeout(function(){
                func.apply(context, args)
            }, wait);
        }
    }
}

const debounceCalcute = {
    'txt2img_generate': debounceCalcuteTimes(calcuCreditTimes, 'txt2img_generate'),
    'img2img_generate': debounceCalcuteTimes(calcuCreditTimes, 'img2img_generate'),
};


async function calcuCreditTimes(width, height, batch_count, batch_size, steps, buttonId, hr_scale = 1, hr_second_pass_steps = 0, enable_hr = false) {
    try {
        const response = await fetch(`/api/calculateConsume`, {
            method: "POST",
            credentials: "include",
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: buttonId.split('_')[0],
                image_sizes: [
                    {
                        width,
                        height
                    }
                ],
                batch_count,
                batch_size,
                steps,
                scale: hr_scale,
                hr_second_pass_steps,
                hr_scale,
                enable_hr
            })
        });
        const { inference } = await response.json();
        const buttonEle = gradioApp().querySelector(`#${buttonId}`);
        //buttonEle.innerHTML = `Generate <span>(Use ${inference} ${inference === 1 ? 'credit)': 'credits)'}</span> `;
    } catch(e) {
        console.log(e);
    }

}

function updateGenerateBtn_txt2img(width = 512, height = 512, batch_count = 1, batch_size = 1, steps = 20, hr_scale = 1, enable_hr = false, hr_second_pass_steps = 0) {
    debounceCalcute['txt2img_generate'](width, height, batch_count, batch_size, steps, 'txt2img_generate', hr_scale, hr_second_pass_steps, enable_hr);
}

function updateGenerateBtn_img2img(width = 512, height = 512, batch_count = 1, batch_size = 1, steps = 20) {
    debounceCalcute['img2img_generate'](width, height, batch_count, batch_size, steps, 'img2img_generate');
}


function ask_for_style_name(_, prompt_text, negative_prompt_text) {
    var name_ = prompt('Style name:');
    return [name_, prompt_text, negative_prompt_text];
}

function confirm_clear_prompt(prompt, negative_prompt) {
    if (confirm("Delete prompt?")) {
        prompt = "";
        negative_prompt = "";
    }

    return [prompt, negative_prompt];
}


var opts = {};
onAfterUiUpdate(function() {
    if (Object.keys(opts).length != 0) return;

    var json_elem = gradioApp().getElementById('settings_json');
    if (json_elem == null) return;

    var textarea = json_elem.querySelector('textarea');
    var jsdata = textarea.value;
    opts = JSON.parse(jsdata);

    executeCallbacks(optionsAvailableCallbacks); /*global optionsAvailableCallbacks*/
    executeCallbacks(optionsChangedCallbacks); /*global optionsChangedCallbacks*/

    Object.defineProperty(textarea, 'value', {
        set: function(newValue) {
            var valueProp = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
            var oldValue = valueProp.get.call(textarea);
            valueProp.set.call(textarea, newValue);

            if (oldValue != newValue) {
                opts = JSON.parse(textarea.value);
            }

            executeCallbacks(optionsChangedCallbacks);
        },
        get: function() {
            var valueProp = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
            return valueProp.get.call(textarea);
        }
    });

    json_elem.parentElement.style.display = "none";
});

onOptionsChanged(function() {
    var elem = gradioApp().getElementById('sd_checkpoint_hash');
    var sd_checkpoint_hash = opts.sd_checkpoint_hash || "";
    var shorthash = sd_checkpoint_hash.substring(0, 10);

    if (elem && elem.textContent != shorthash) {
        elem.textContent = shorthash;
        elem.title = sd_checkpoint_hash;
        elem.href = "https://google.com/search?q=" + sd_checkpoint_hash;
    }
});

let txt2img_textarea, img2img_textarea = undefined;

function restart_reload() {
    document.body.style.backgroundColor = "var(--background-fill-primary)";
    document.body.innerHTML = '<h1 style="font-family:monospace;margin-top:20%;color:lightgray;text-align:center;">Reloading...</h1>';
    var requestPing = function() {
        requestGet("./internal/ping", {}, function(data) {
            location.reload();
        }, function() {
            setTimeout(requestPing, 500);
        });
    };

    setTimeout(requestPing, 2000);

    return [];
}

// Simulate an `input` DOM event for Gradio Textbox component. Needed after you edit its contents in javascript, otherwise your edits
// will only visible on web page and not sent to python.
function updateInput(target) {
    let e = new Event("input", {bubbles: true});
    Object.defineProperty(e, "target", {value: target});
    target.dispatchEvent(e);
}


var desiredCheckpointName = null;
function selectCheckpoint(name) {
    desiredCheckpointName = name;
    gradioApp().getElementById('change_checkpoint').click();
}
var desiredVAEName = 0;
function selectVAE(vae) {
    desiredVAEName = vae;
}

function currentImg2imgSourceResolution(w, h, scaleBy) {
    var img = gradioApp().querySelector('#mode_img2img > div[style="display: block;"] :is(img, canvas)');
    const img2imgScaleDom = gradioApp().querySelector("#img2img_scale");
    const sliderDom = img2imgScaleDom.querySelector("input[type='range']");
    const inputDom = img2imgScaleDom.querySelector("input[type='number']");
    const maxImgSizeLimit = 4096;
    if (img) {
        const maxScale = Math.min(Math.floor(maxImgSizeLimit / img.naturalWidth), Math.floor(maxImgSizeLimit / img.naturalHeight)).toFixed(2);
        if (sliderDom.max !== maxScale) {
            sliderDom.max = maxScale;
            inputDom.max = maxScale;
        }
        return [img.naturalWidth, img.naturalHeight, scaleBy]
    }

    return [0, 0, scaleBy];
}

function detectImageSize() {
    const [width, height, _] = currentImg2imgSourceResolution(0, 0, 0);
    return [
        { value: width, __type__: "update" },
        { value: height, __type__: "update" },
    ];
}

function updateImg2imgResizeToTextAfterChangingImage() {
    // At the time this is called from gradio, the image has no yet been replaced.
    // There may be a better solution, but this is simple and straightforward so I'm going with it.

    setTimeout(function() {
        gradioApp().getElementById('img2img_update_resize_to').click();
    }, 500);

    return [];

}

function setRandomSeed(elem_id) {
    var input = gradioApp().querySelector("#" + elem_id + " input");
    if (!input) return [];

    input.value = "-1";
    updateInput(input);
    return [];
}

function switchWidthHeight(tabname) {
    var width = gradioApp().querySelector("#" + tabname + "_width input[type=number]");
    var height = gradioApp().querySelector("#" + tabname + "_height input[type=number]");
    if (!width || !height) return [];

    var tmp = width.value;
    width.value = height.value;
    height.value = tmp;

    updateInput(width);
    updateInput(height);
    return [];
}

let uiPageSize;

function setUiPageSize() {
    const contentWidth = document.body.clientWidth - 84;
    uiPageSize = Math.floor(contentWidth / 238) * 2;
}

function requestRefreshPage() {
    getDiffusApp().openRefreshDialog(async () => {
        location.reload();
    });
}


async function checkSignatureCompatibility() {
    const currentSignatureHash = gradioApp().querySelector("#signature_hash textarea").value;

    const response = await fetchGet("internal/signature/hash", {mode: "cors"});
    
    const redirectUrl = new URL(response.url);
    if (window.location.hostname !== redirectUrl.hostname) {
        requestRefreshPage();
        console.log('Redirected to a new domain:', redirectUrl.hostname);
        return;
    }
    
    if (response.status !== 200) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    if (data.signature_hash !== currentSignatureHash) {
        requestRefreshPage();
    }
}

const SIGNATURE_CHECK_INTERVAL = 10 * 60 * 1000; // 10 minutes

async function monitorSignatureChange() {
    while(true) {
        try {
            await PYTHON.asyncio.sleep(SIGNATURE_CHECK_INTERVAL);
            
            if (!getDiffusApp().webUI.showWebUI()) {
                continue;
            }
            
            await checkSignatureCompatibility();
        } catch (error) {
            console.error("Error in monitorSignatureChange:", error);
        }
    }
}

function on_sd_model_selection_updated(model_title){
    return [model_title, model_title]
}

function initPerfectScrollbar() {
    const ps = new PerfectScrollbar(gradioApp().getElementsByClassName("app")[0])
}

// get user info
onUiLoaded(function(){
    setUiPageSize();
    initPerfectScrollbar();

    // update generate button text
    updateGenerateBtn_txt2img();
    updateGenerateBtn_img2img();

    const {search} = location;
    const isDarkTheme = /theme=dark/g.test(search);
    Cookies.set('theme', isDarkTheme ? 'dark' : 'light');

    monitorSignatureChange();
});

var onEditTimers = {};

// calls func after afterMs milliseconds has passed since the input elem has been edited by user
function onEdit(editId, elem, afterMs, func) {
    var edited = function() {
        var existingTimer = onEditTimers[editId];
        if (existingTimer) clearTimeout(existingTimer);

        onEditTimers[editId] = setTimeout(func, afterMs);
    };

    elem.addEventListener("input", edited);

    return edited;
}
