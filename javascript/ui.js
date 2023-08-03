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
    var allCurrentButtons = gradioApp().querySelectorAll('[style="display: block;"].tabitem div[id$=_gallery].gradio-gallery .thumbnail-item.thumbnail-small.selected');
    var visibleCurrentButton = null;
    allCurrentButtons.forEach(function(elem) {
        if (elem.parentElement.offsetParent) {
            visibleCurrentButton = elem;
        }
    });
    return visibleCurrentButton;
}

function selected_gallery_index() {
    var buttons = all_gallery_buttons();
    var button = selected_gallery_button();

    var result = -1;
    buttons.forEach(function(v, i) {
        if (v == button) {
            result = i;
        }
    });

    return result;
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

function switch_to_txt2img() {
    gradioApp().querySelector('#tabs').querySelectorAll('button')[0].click();

    return Array.from(arguments);
}

function switch_to_img2img_tab(no) {
    gradioApp().querySelector('#tabs').querySelectorAll('button')[1].click();
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
    gradioApp().querySelector('#tabs').querySelectorAll('button')[2].click();

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
    res[0] = get_tab_index('mode_img2img');
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

function showSubmitButtons(tabname, show) {
    gradioApp().getElementById(tabname + '_interrupt').style.display = show ? "none" : "block";
    gradioApp().getElementById(tabname + '_skip').style.display = show ? "none" : "block";
}

function showRestoreProgressButton(tabname, show) {
    var button = gradioApp().getElementById(tabname + "_restore_progress");
    if (!button) return;

    button.style.display = show ? "flex" : "none";
}

function submit() {
    checkSignatureCompatibility();

    showSubmitButtons('txt2img', false);

    var id = randomId();
    localStorage.setItem("txt2img_task_id", id);

    requestProgress(id, gradioApp().getElementById('txt2img_gallery_container'), gradioApp().getElementById('txt2img_gallery'), function() {
        showSubmitButtons('txt2img', true);
        localStorage.removeItem("txt2img_task_id");
        showRestoreProgressButton('txt2img', false);
    });

    var res = create_submit_args(arguments);

    res[0] = id;

    if (typeof posthog === 'object') {
      posthog.capture('txt2img generation button clicked');
    }

    return res;
}

function submit_img2img() {
    showSubmitButtons('img2img', false);

    var id = randomId();
    localStorage.setItem("img2img_task_id", id);

    requestProgress(id, gradioApp().getElementById('img2img_gallery_container'), gradioApp().getElementById('img2img_gallery'), function() {
        showSubmitButtons('img2img', true);
        localStorage.removeItem("img2img_task_id");
        showRestoreProgressButton('img2img', false);
    });

    var res = create_submit_args(arguments);

    res[0] = id;
    res[1] = get_tab_index('mode_img2img');

    if (typeof posthog === 'object') {
      posthog.capture('img2img generation button clicked');
    }

    return res;
}

function restoreProgressTxt2img() {
    showRestoreProgressButton("txt2img", false);
    var id = localStorage.getItem("txt2img_task_id");

    id = localStorage.getItem("txt2img_task_id");

    if (id) {
        requestProgress(id, gradioApp().getElementById('txt2img_gallery_container'), gradioApp().getElementById('txt2img_gallery'), function() {
            showSubmitButtons('txt2img', true);
        }, null, 0);
    }

    return id;
}

function restoreProgressImg2img() {
    showRestoreProgressButton("img2img", false);

    var id = localStorage.getItem("img2img_task_id");

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

onUiLoaded(function() {
    showRestoreProgressButton('txt2img', localStorage.getItem("txt2img_task_id"));
    showRestoreProgressButton('img2img', localStorage.getItem("img2img_task_id"));
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
        buttonEle.innerHTML = `Generate <span>(Use ${inference} ${inference === 1 ? 'credit)': 'credits)'}</span> `;
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

    setupTokenCounters();

    var show_all_pages = gradioApp().getElementById('settings_show_all_pages');
    var settings_tabs = gradioApp().querySelector('#settings div');
    if (show_all_pages && settings_tabs) {
        settings_tabs.appendChild(show_all_pages);
        show_all_pages.onclick = function() {
            gradioApp().querySelectorAll('#settings > div').forEach(function(elem) {
                if (elem.id == "settings_tab_licenses") {
                    return;
                }

                elem.style.display = "block";
            });
        };
    }
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

function redirect_to_payment(need_upgrade){
    if (need_upgrade) {
        window.location.href = "/user?upgradeFlag=true";
    }
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

function browseWorkspaceModels() {
    var txt2img_tab = gradioApp().querySelector("#tab_txt2img");
    var img2img_tab = gradioApp().querySelector("#tab_img2img");
    var txt2img_button = gradioApp().querySelector("#txt2img_extra_networks");
    var img2img_button = gradioApp().querySelector("#img2img_extra_networks");

    if (txt2img_tab.style.display === "block") {
        txt2img_button.click();
    }

    if (img2img_tab.style.display === "block") {
        img2img_button.click();
    }

    const browseModelsBtn = gradioApp().querySelector('#browse_models_in_workspace');
    if (gradioApp().querySelector("div#img2img_extra_networks").classList.contains("hide") && gradioApp().querySelector("div#txt2img_extra_networks").classList.contains("hide")) {
        browseModelsBtn.textContent = 'Hide workspace models';
    } else {
        browseModelsBtn.textContent = 'Show workspace models';
    }
    
}

async function browseModels(){
    var txt2img_tab = gradioApp().querySelector("#tab_txt2img");
    var img2img_tab = gradioApp().querySelector("#tab_img2img");
    var txt2img_model_refresh_button = gradioApp().querySelector('#txt2img_extra_refresh');
    var img2img_model_refresh_button = gradioApp().querySelector('#img2img_extra_refresh');
    // if (txt2img_tab.style.display == "none" && img2img_tab.style.display == "none")
    // {
    //     var txt2img_tab_button = document.querySelector("#tabs > div.tab-nav > button:nth-child(1)");
    //     txt2img_tab_button.click();
    //     await new Promise(r => setTimeout(r, 100));
    // }

    if (txt2img_tab.style.display == "block")
    {
        if (gradioApp().querySelector("div#txt2img_extra_networks").classList.contains("hide"))
        {
            fetchHomePageDataAndUpdateList({tabname: 'txt2img', model_type: currentTab.get('txt2img'), page: 1});
        }
        
    }

    
    if (img2img_tab.style.display == "block")
    {
        if (gradioApp().querySelector("div#img2img_extra_networks").classList.contains("hide"))
        {
            fetchHomePageDataAndUpdateList({tabname: 'img2img', model_type: currentTab.get('img2img'), page: 1});
        }
    }
}

let uiPageSize;

function setUiPageSize() {
    const contentWidth = document.body.clientWidth - 84;
    uiPageSize = Math.floor(contentWidth / 238) * 2;
}

function searchModel({page_name, searchValue}) {
    const requestUrl = connectNewModelApi ? `/internal/favorite_models?model_type=${model_type_mapper[page_name]}&search_value=${searchValue}&page=1&page_size=${uiPageSize}` 
        : `/sd_extra_networks/models?page_name=${page_name}&page=1&search_value=${searchValue}&page_size=${uiPageSize}&need_refresh=false`;
    return fetchGet(requestUrl);
}

function searchPublicModel({page_name, searchValue}) {
    const requestUrl = connectNewModelApi ? `/internal/models?model_type=${model_type_mapper[page_name]}&search_value=${searchValue}&page=1&page_size=${uiPageSize}` 
        : `/sd_extra_networks/models?page_name=${page_name}&page=1&search_value=${searchValue}&page_size=${uiPageSize}&need_refresh=false`;
    return fetchGet(requestUrl);
}

async function getModelFromUrl() {

    // get model form url
    const urlParam = new URLSearchParams(location.search);
    // const checkpointModelValueFromUrl = urlParam.get('checkpoint');

    // document.cookie = `selected_checkpoint_model=${checkpointModelValueFromUrl}`;
    const keyMapModelType = {
        "checkpoint": "checkpoints",
        "c": "checkpoints",
        "lora": "lora",
        "l": "lora",
        "ti": "textual_inversion",
        "t": "textual_inversion",
        "hn": "hypernetworks",
        "h": "hypernetworks",
        "lycoris": "lycoris",
        "y": "lycoris",
    }

    const promiseList = [];
    const urlList = Array.from(urlParam.entries());
    const urlKeys =  [];
    const urlValues =  [];
    let checkpoint = null;

    for (const [key, value] of urlList) {
        if (keyMapModelType[key]) {
            if (checkpoint) {
                notifier.alert('There are multiple checkpoint in the url, we will use the first one and discard the rest')
                break;
            }
            if (key === 'checkpoint') {
                checkpoint = value;
            }
            // query is in public models
            const publicModelResponse = searchPublicModel({ page_name: keyMapModelType[key], searchValue: value.toLowerCase() })
            promiseList.push(publicModelResponse);
            urlKeys.push(key);
            urlValues.push(value);
        }
    }

    if(promiseList.length === 0) return;
    const allPromise = Promise.all(promiseList);

    notifier.asyncBlock(allPromise, async (promisesRes) => {
        promisesRes.forEach(async (publicModelResponse, index) => {
            if (publicModelResponse && publicModelResponse.status === 200) {
                const { model_list, allow_negative_prompt } = await publicModelResponse.json();
                if (model_list && model_list.length > 0) {
                        // add to personal workspace
                        const res = await fetchPost({ data: {model_id: model_list[0].id}, url: `/internal/favorite_models` });
                        if(res.status === 200) {
                            notifier.success(`Added model ${model_list[0].name} to your workspace successfully.`)
                        } else if (res.status === 409) {
                            const { detail } = await res.json();
                            notifier.info(detail);
                        } else {
                            notifier.alert(`Added model ${model_list[0].name} to your workspace Failed`)
                        }
                        if(urlKeys[index] === 'checkpoint') {
                            // checkpoint dont need to replace text
                            selectCheckpoint(model_list[0].sha256 || model_list[0].shorthash || model_list[0].name);
                        } else {
                            if (model_list[0].prompt) {
                                cardClicked('txt2img', eval(model_list[0].prompt), allow_negative_prompt);
                            }
                        }
                } else {
                    fetchPost({
                        data: {"sha256": urlValues[index]},
                        url: "/download-civitai-model"
                    })
                    notifier.warning(`We could not find model (${urlValues[index]}) in our library. Trying to download it from Civitai, it could take up to 5 minutes. Meanwhile, feel free to check out thousands of models already in our library.`, {
                        labels: {
                            warning: 'DOWNLOADIND MODEL'
                        }
                    })
                }
             } else {
                notifier.alert(`Query Failed`);
             }
        })
    });
    
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

function getSubscribers(interval = 10, timeoutId = null)
{
    const latestSubscribers = fetchGet(`/subscriptions/latest?interval=${interval}`);
    latestSubscribers.then(async (response) => {
        if (response.ok) {
            const newSubscribers = await response.json();
            if (newSubscribers.current_tier != "free") {
                if (timeoutId) {
                    clearTimeout(timeoutId);
                }
            } else {
                newSubscribers.subscribers.forEach((newSubscriber) => {
                    const notificationElem = notifier.success(
                        `<div class="notification-sub-main" style="width: 285px"><b class="notification-sub-email">${newSubscriber.email}</b> just subscribed to our basic plan &#129395 <a class="notification-upgrade-hyperlink" href="/user#/subscription?type=subscription" target="_blank">Click here to upgrade</a> and enjoy 5000 credits monthly!</div>`,
                        {labels: {success: ""}, animationDuration: 800, durations: {success: 8000}}
                    );
                    if (typeof posthog === 'object') {
                        notificationElem.querySelector(".notification-upgrade-hyperlink").addEventListener("click", () => {
                            posthog.capture('Notification upgrade link clicked', {
                                subscriber_email: newSubscriber.email,
                            });
                        });
                    }
                });
            }
        }
    });
}

async function checkSignatureCompatibility(timeoutId = null)
{
    const txt2imgSignaturePromise = fetchGet("/internal/signature/txt2img");
    const img2imgSignaturePromise = fetchGet("/internal/signature/img2img");

    const currentTxt2imgSignature = gradioApp().querySelector("#txt2img_signature textarea").value;
    const currentTxt2imgFnIndex = gradioApp().querySelector("#txt2img_function_index textarea").value;
    const currentImg2imgSignature = gradioApp().querySelector("#img2img_signature textarea").value;
    const currentImg2imgFnIndex = gradioApp().querySelector("#img2img_function_index textarea").value;

    let needRefresh = false;

    txt2imgSignaturePromise.then(async (response) => {
        if (response.ok) {
            const txt2imgSignature = await response.json();
            if ((txt2imgSignature.signature != currentTxt2imgSignature || txt2imgSignature.fn_index != currentTxt2imgFnIndex) && !needRefresh)
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
    });
    img2imgSignaturePromise.then(async (response) => {
        if (response.ok) {
            const img2imgSignature = await response.json();
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
    });
}

async function monitorSignatureChange() {
    const timeoutId = setTimeout(monitorSignatureChange, 30000);
    checkSignatureCompatibility(timeoutId);
}

async function pullNewSubscribers() {
    const interval = 10;
    const timeoutId = setTimeout(pullNewSubscribers, interval * 1000);
    getSubscribers(interval, timeoutId);
}

function getCurrentUserName() {
    const userName = gradioApp().querySelector(
        "div.user_info > div > span").textContent;
    return userName;
}

function getCurrentUserAvatar() {
    const userAvatarUrl = gradioApp().querySelector(
        "div.user_info > a > img").src;
    return userAvatarUrl;
}

async function joinShareGroupWithId(share_id, userName=null, userAvatarUrl=null) {
    if (!userName) {
        userName = getCurrentUserName();
    }
    if (!userAvatarUrl) {
        userAvatarUrl = getCurrentUserAvatar();
    }
    if (share_id) {
        fetch('/share/group/join', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                group_info: {
                    share_id: share_id
                },
                avatar: {
                    avatar_url: userAvatarUrl,
                    user_name: userName
                }
            })
        })
        .then(response => {
            if (response.status === 200) {
                return response.json();
            }
            return Promise.reject(response);
        })
        .then(async (data) => {
            if (data.event_code != 202) {
                fetch('/share/group/join/html', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        user_name: userName,
                        user_avatar_url: userAvatarUrl,
                        event_code: data.event_code,
                        share_group: data.share_group
                    })
                })
                .then(response => {
                    if (response.status === 200) {
                        return response.text();
                    }
                    return Promise.reject(response);
                })
                .then((htmlResponse) => {
                    let doc = document.implementation.createHTMLDocument();
                    doc.body.innerHTML = htmlResponse;
                    let arrayScripts = [].map.call(doc.getElementsByTagName('script'), function(el) {
                        return el;
                    });
                    for (const index in arrayScripts) {
                        doc.body.removeChild(arrayScripts[index]);
                    }
                    notifier.modal(doc.body.innerHTML);
                    for (const index in arrayScripts) {
                        let new_script = document.createElement("script");
                        if (arrayScripts[index].src) {
                            new_script.src = arrayScripts[index].src;
                        } else {
                            new_script.innerHTML = arrayScripts[index].innerHTML;
                        }
                        document.body.appendChild(new_script);
                    }
                })
                .catch((error) => {
                    console.error('Error:', error);
                });
            }
        })
        .catch((error) => {
            console.error('Error:', error);
        });
    }
}

async function joinShareGroup(userName=null, avatarUrl=null) {
    const urlParams = new URLSearchParams(window.location.search);
    const share_id = urlParams.get('share_id');

    joinShareGroupWithId(share_id, userName, avatarUrl);
}

// get user info
onUiLoaded(function(){
    setUiPageSize();
    // update generate button text
    updateGenerateBtn_txt2img();
    updateGenerateBtn_img2img();

    getModelFromUrl();

    const {search} = location;
    const isDarkTheme = /theme=dark/g.test(search);
    if (isDarkTheme) {
        const rightContent = gradioApp().querySelector(".right-content");
        const imgNodes = rightContent.querySelectorAll("a > img");
        imgNodes.forEach(item => {
            item.style.filter = 'invert(100%)';
        })
    }

    setTimeout(monitorSignatureChange, 30000);
    pullNewSubscribers();
   

    fetch(`/api/order_info`, {method: "GET", credentials: "include"}).then(res => {
        if (res && res.ok && !res.redirected) {
            return res.json();
        }
    }).then(result => {
        if (result) {
                const userContent = gradioApp().querySelector(".user-content");
                const userInfo = userContent.querySelector(".user_info");
                if (userInfo) {
                    userInfo.style.display = 'flex';
                    const img = userInfo.querySelector("a > img");
                    if (img) {
                        imgExists(result.picture, img, result.name);
                    }
                    const name = userInfo.querySelector(".user_info-name > span");
                    if (name) {
                        name.innerHTML = result.name;
                    }
                    const logOutLink = userInfo.querySelector(".user_info-name > a");
                    if (logOutLink) {
                        logOutLink.target="_self";
                        // remove cookie
                        logOutLink.onclick = () => {
                            document.cookie = 'auth-session=;';
                        }
                    }

                    if (result.tier === 'Free') {
                        const upgradeContent = userContent.querySelector("#upgrade");
                        if (upgradeContent) {
                            upgradeContent.style.display = 'flex';
                        }
                    }

                    if (result.tier === 'Basic') {
                        const packageIcon = gradioApp().querySelector('#package');
                        if (packageIcon) {
                            packageIcon.style.display = 'flex';
                            const aLink = packageIcon.querySelector('a');
                            const spanNode = aLink.querySelector('span');
                            const resultInfo = {"user_id": result.user_id};
                            const referenceId = Base64.encodeURI(JSON.stringify(resultInfo));
                            const host = judgeEnvironment() === 'prod' ? 'https://buy.stripe.com/00g7sF1K90IXa0UeV5' : 'https://buy.stripe.com/test_9AQ15Uewh6kEb2o9AF';
                            aLink.href = `${host}?prefilled_email=${result.email}&client_reference_id=${referenceId}`;
                            spanNode.textContent = isPcScreen ? 'Credits Package' : '';
                        }
                    }
                }
        }
    })
});
