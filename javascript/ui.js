// various functions for interaction with ui.py not large enough to warrant putting them in separate files

function set_theme(theme) {
    var gradioURL = window.location.href;
    const searchParam = new URLSearchParams(window.location.search);
    if (!gradioURL.includes('__theme=')) {
      window.location.replace(`${window.location.origin}?${searchParam}&__theme=${theme}`);
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

function extract_image_from_gallery(gallery) {
    if (gallery.length == 0) {
        return [null];
    }
    if (gallery.length == 1) {
        return [gallery[0]];
    }

    var index = selected_gallery_index();

    if (index < 0 || index >= gallery.length) {
        // Use the first image in the gallery as the default
        index = 0;
    }

    return [gallery[index]];
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

function switch_to_svd() {
    switchToTab("tab_svd");
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
        res[res.length - 4] = null;
    }

    return res;
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
    var button = gradioApp().getElementById(tabname + "_restore_progress");
    if (!button) return;

    button.style.display = show ? "flex" : "none";
}

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
    reportSpendCreditsEvent(itemName, credits);
}

async function _submit() {
    var res = create_submit_args(arguments);
    const [all_style_info_index, all_style_info] = await getAllStyleInfo(res);
    const [all_model_info_index, all_model_info] = await getAllModelInfo("txt2img", res, all_style_info);

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

async function submit() {
    addGenerateGtagEvent("#txt2img_generate > span", "txt2img_generation_button");
    await tierCheckGenerate("txt2img", arguments);
    checkSignatureCompatibility();

    return await _submit(...arguments);
}

async function submit_txt2img_upscale() {
    var res = await _submit(...arguments);

    res[2] = selected_gallery_index();

    return res;
}

async function submit_img2img() {
    addGenerateGtagEvent("#img2img_generate > span", "img2img_generation_button");
    await tierCheckGenerate("img2img", arguments);
    showSubmitButtons('img2img', false);

    var res = create_submit_args(arguments);
    const [all_style_info_index, all_style_info] = await getAllStyleInfo(res);
    const [all_model_info_index, all_model_info] = await getAllModelInfo("img2img", res, all_style_info);

    var id = randomId();
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

function submit_extras() {
    showSubmitButtons('extras', false);

    var id = randomId();
    localStorage.setItem("txt2img_task_id", id);

    requestProgress(id, gradioApp().getElementById('extras_gallery_container'), gradioApp().getElementById('extras_gallery'), function() {
        showSubmitButtons('extras', true);
    });

    var res = create_submit_args(arguments);

    res[0] = id;

    console.log(res);
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

function currentImg2imgSourceResolution(w, h, scaleBy) {
    var img = gradioApp().querySelector('#mode_img2img > div[style="display: block;"] img');
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

function imgExists(url, imgNode, name){
    const img = new Image();
    img.src= url;
    img.onerror = () => {
        imgNode.src = `https://ui-avatars.com/api/?name=${name}&background=random&format=svg`
        joinShareGroup(name, imgNode.src);
    }
    img.onload = () => {
        imgNode.src = url;
        joinShareGroup(name, url);
    }
}

function requestRefreshPage(timeoutId) {
    let onRefresh = () => {location.reload();};
    if (timeoutId)
    {
        clearTimeout(timeoutId);
    }
    notifier.confirm(
        'We have just updated the service with new features. Click the button to refresh to enjoy the new features.',
        onRefresh,
        false,
        {
            labels: {
            confirm: 'Page Need Refresh'
            }
        }
    );
}

async function checkSignatureCompatibility(timeoutId = null)
{
    const currentDomain = window.location.hostname;
    const txt2imgSignaturePromise = fetchGet("/internal/signature/txt2img", {mode: "cors"});
    const img2imgSignaturePromise = fetchGet("/internal/signature/img2img", {mode: "cors"});

    const currentTxt2imgSignature = gradioApp().querySelector("#txt2img_signature textarea").value;
    const currentTxt2imgFnIndex = gradioApp().querySelector("#txt2img_function_index textarea").value;
    const currentImg2imgSignature = gradioApp().querySelector("#img2img_signature textarea").value;
    const currentImg2imgFnIndex = gradioApp().querySelector("#img2img_function_index textarea").value;

    let needRefresh = false;

    txt2imgSignaturePromise
    .then(response => {
        const redirectUrl = new URL(response.url);
        const redirectDomain = redirectUrl.hostname;
        if (currentDomain !== redirectDomain) {
            needRefresh = true;
            requestRefreshPage(timeoutId);
            console.log('Redirected to a new domain:', redirectDomain);
            return Promise.reject(response);
        } else {
            if (response.status === 200) {
                return response.json();
            }
            return Promise.reject(response);
        }
    })
    .then((txt2imgSignature) => {
        if (txt2imgSignature && txt2imgSignature.signature && txt2imgSignature.fn_index) {
            if ((txt2imgSignature.signature != currentTxt2imgSignature || txt2imgSignature.fn_index != currentTxt2imgFnIndex) && !needRefresh)
            {
                needRefresh = true;
                requestRefreshPage(timeoutId);
            }
        }
    })
    .catch((error) => {
        console.error('Error:', error);
    });

    img2imgSignaturePromise
    .then(response => {
        if (response.status === 200) {
            return response.json();
        }
        return Promise.reject(response);
    })
    .then((img2imgSignature) => {
        if (img2imgSignature && img2imgSignature.signature && img2imgSignature.fn_index) {
            if ((img2imgSignature.signature != currentImg2imgSignature || img2imgSignature.fn_index != currentImg2imgFnIndex) && !needRefresh)
            {
                let onRefresh = () => {location.reload();};
                needRefresh = true;
                if (timeoutId)
                {
                    clearTimeout(timeoutId);
                }
               notifier.confirm(
                   'We have just updated the service with new features. Click the button to refresh to enjoy the new features.',
                   onRefresh,
                   false,
                   {
                       labels: {
                       confirm: 'Page Need Refresh'
                       }
                   }
               );
            }
        }
    })
    .catch((error) => {
        console.error('Error:', error);
    });
}

async function monitorSignatureChange() {
    const timeoutId = setTimeout(monitorSignatureChange, 30000);
    checkSignatureCompatibility(timeoutId);
}

function on_sd_model_selection_updated(model_title){
    return [model_title, model_title]
}

// get user info
onUiLoaded(function(){
    setUiPageSize();
    // update generate button text
    updateGenerateBtn_txt2img();
    updateGenerateBtn_img2img();

    checkModelURLFromCivitai();

    const {search} = location;
    const isDarkTheme = /theme=dark/g.test(search);
    Cookies.set('theme', isDarkTheme ? 'dark' : 'light');
    if (isDarkTheme) {
        const rightContent = gradioApp().querySelector(".right-content");
        const imgNodes = rightContent.querySelectorAll("a > img");
        imgNodes.forEach(item => {
            item.style.filter = 'invert(100%)';
        })
    }

    setTimeout(monitorSignatureChange, 30000);
});

var onEditTimers = {};

// calls func after afterMs milliseconds has passed since the input elem has beed enited by user
function onEdit(editId, elem, afterMs, func) {
    var edited = function() {
        var existingTimer = onEditTimers[editId];
        if (existingTimer) clearTimeout(existingTimer);

        onEditTimers[editId] = setTimeout(func, afterMs);
    };

    elem.addEventListener("input", edited);

    return edited;
}
