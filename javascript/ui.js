// various functions for interaction with ui.py not large enough to warrant putting them in separate files

function set_theme(theme){
    gradioURL = window.location.href;
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
    })
    return visibleGalleryButtons;
}

function selected_gallery_button() {
    var allCurrentButtons = gradioApp().querySelectorAll('[style="display: block;"].tabitem div[id$=_gallery].gradio-gallery .thumbnail-item.thumbnail-small.selected');
    var visibleCurrentButton = null;
    allCurrentButtons.forEach(function(elem) {
        if (elem.parentElement.offsetParent) {
            visibleCurrentButton = elem;
        }
    })
    return visibleCurrentButton;
}

function selected_gallery_index(){
    var buttons = all_gallery_buttons();
    var button = selected_gallery_button();

    var result = -1
    buttons.forEach(function(v, i){ if(v==button) { result = i } })

    return result
}

function extract_image_from_gallery(gallery){
    if (gallery.length == 0){
        return [null];
    }
    if (gallery.length == 1){
        return [gallery[0]];
    }

    index = selected_gallery_index()

    if (index < 0 || index >= gallery.length){
        // Use the first image in the gallery as the default
        index = 0;
    }

    return [gallery[index]];
}

function args_to_array(args){
    res = []
    for(var i=0;i<args.length;i++){
        res.push(args[i])
    }
    return res
}

function switch_to_txt2img(){
    gradioApp().querySelector('#tabs').querySelectorAll('button')[0].click();

    return args_to_array(arguments);
}

function switch_to_img2img_tab(no){
    gradioApp().querySelector('#tabs').querySelectorAll('button')[1].click();
    gradioApp().getElementById('mode_img2img').querySelectorAll('button')[no].click();
}
function switch_to_img2img(){
    switch_to_img2img_tab(0);
    return args_to_array(arguments);
}

function switch_to_sketch(){
    switch_to_img2img_tab(1);
    return args_to_array(arguments);
}

function switch_to_inpaint(){
    switch_to_img2img_tab(2);
    return args_to_array(arguments);
}

function switch_to_inpaint_sketch(){
    switch_to_img2img_tab(3);
    return args_to_array(arguments);
}

function switch_to_inpaint(){
    gradioApp().querySelector('#tabs').querySelectorAll('button')[1].click();
    gradioApp().getElementById('mode_img2img').querySelectorAll('button')[2].click();

    return args_to_array(arguments);
}

function switch_to_extras(){
    gradioApp().querySelector('#tabs').querySelectorAll('button')[2].click();

    return args_to_array(arguments);
}

function get_tab_index(tabId){
    var res = 0

    gradioApp().getElementById(tabId).querySelector('div').querySelectorAll('button').forEach(function(button, i){
        if(button.className.indexOf('selected') != -1)
            res = i
    })

    return res
}

function create_tab_index_args(tabId, args){
    var res = []
    for(var i=0; i<args.length; i++){
        res.push(args[i])
    }

    res[0] = get_tab_index(tabId)

    return res
}

function get_img2img_tab_index() {
    let res = args_to_array(arguments)
    res.splice(-2)
    res[0] = get_tab_index('mode_img2img')
    return res
}

function create_submit_args(args){
    res = []
    for(var i=0;i<args.length;i++){
        res.push(args[i])
    }

    // As it is currently, txt2img and img2img send back the previous output args (txt2img_gallery, generation_info, html_info) whenever you generate a new image.
    // This can lead to uploading a huge gallery of previously generated images, which leads to an unnecessary delay between submitting and beginning to generate.
    // I don't know why gradio is sending outputs along with inputs, but we can prevent sending the image gallery here, which seems to be an issue for some.
    // If gradio at some point stops sending outputs, this may break something
    if(Array.isArray(res[res.length - 3])){
        res[res.length - 3] = null
    }

    return res
}

function showSubmitButtons(tabname, show){
    gradioApp().getElementById(tabname+'_interrupt').style.display = show ? "none" : "block"
    gradioApp().getElementById(tabname+'_skip').style.display = show ? "none" : "block"
}

function showRestoreProgressButton(tabname, show){
    button = gradioApp().getElementById(tabname + "_restore_progress")
    if(! button) return

    button.style.display = show ? "flex" : "none"
}

function submit(){
    rememberGallerySelection('txt2img_gallery')
    showSubmitButtons('txt2img', false)

    var id = randomId()
    localStorage.setItem("txt2img_task_id", id);

    requestProgress(id, gradioApp().getElementById('txt2img_gallery_container'), gradioApp().getElementById('txt2img_gallery'), function(){
        showSubmitButtons('txt2img', true)
        localStorage.removeItem("txt2img_task_id")
        showRestoreProgressButton('txt2img', false)
    })

    var res = create_submit_args(arguments)

    res[0] = id

    return res
}

function submit_img2img(){
    rememberGallerySelection('img2img_gallery')
    showSubmitButtons('img2img', false)

    var id = randomId()
    localStorage.setItem("img2img_task_id", id);

    requestProgress(id, gradioApp().getElementById('img2img_gallery_container'), gradioApp().getElementById('img2img_gallery'), function(){
        showSubmitButtons('img2img', true)
        localStorage.removeItem("img2img_task_id")
        showRestoreProgressButton('img2img', false)
    })

    var res = create_submit_args(arguments)

    res[0] = id
    res[1] = get_tab_index('mode_img2img')

    return res
}

function restoreProgressTxt2img(x){
    showRestoreProgressButton("txt2img", false)

    id = localStorage.getItem("txt2img_task_id")

    if(id) {
        requestProgress(id, gradioApp().getElementById('txt2img_gallery_container'), gradioApp().getElementById('txt2img_gallery'), function(){
            showSubmitButtons('txt2img', true)
        }, null, 0)
    }

    return id
}
function restoreProgressImg2img(x){
    showRestoreProgressButton("img2img", false)

    id = localStorage.getItem("img2img_task_id")

    if(id) {
        requestProgress(id, gradioApp().getElementById('img2img_gallery_container'), gradioApp().getElementById('img2img_gallery'), function(){
            showSubmitButtons('img2img', true)
        }, null, 0)
    }

    return id
}


onUiLoaded(function () {
    showRestoreProgressButton('txt2img', localStorage.getItem("txt2img_task_id"))
    showRestoreProgressButton('img2img', localStorage.getItem("img2img_task_id"))
});


function modelmerger(){
    var id = randomId()
    requestProgress(id, gradioApp().getElementById('modelmerger_results_panel'), null, function(){})

    var res = create_submit_args(arguments)
    res[0] = id
    return res
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


async function calcuCreditTimes(width, height, batch_count, batch_size, steps, buttonId, hr_scale = 1) {
    try {
        const response = await fetch(`/api/calculateConsume`, {
            method: "POST", 
            credentials: "include",
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: 'txt2img',
                image_sizes: [
                    {
                        width,
                        height
                    }
                ],
                batch_count,
                batch_size,
                steps,
                scale: hr_scale
            })
        });
        const { inference } = await response.json();
        const buttonEle = gradioApp().querySelector(`#${buttonId}`);
        buttonEle.innerHTML = `Generate <span>(Use ${inference} ${inference === 1 ? 'credit)': 'credits)'}</span> `;
    } catch(e) {
        console.log(e);
    }
    
}

function updateGenerateBtn_txt2img(width = 512, height = 512, batch_count = 1, batch_size = 1, steps = 20, hr_scale = 1, enable_hr) {
    if (enable_hr) {
        debounceCalcute['txt2img_generate'](width, height, batch_count, batch_size, steps, 'txt2img_generate', hr_scale);
    } else {
        debounceCalcute['txt2img_generate'](width, height, batch_count, batch_size, steps, 'txt2img_generate');
    }
    
}

function updateGenerateBtn_img2img(width = 512, height = 512, batch_count = 1, batch_size = 1, steps = 20) {
    debounceCalcute['img2img_generate'](width, height, batch_count, batch_size, steps, 'img2img_generate');
}


function ask_for_style_name(_, prompt_text, negative_prompt_text) {
    name_ = prompt('Style name:')
    return [name_, prompt_text, negative_prompt_text]
}

function confirm_clear_prompt(prompt, negative_prompt) {
    if(confirm("Delete prompt?")) {
        prompt = ""
        negative_prompt = ""
    }

    return [prompt, negative_prompt]
}


promptTokecountUpdateFuncs = {}

function recalculatePromptTokens(name){
    if(promptTokecountUpdateFuncs[name]){
        promptTokecountUpdateFuncs[name]()
    }
}

function recalculate_prompts_txt2img(){
    recalculatePromptTokens('txt2img_prompt')
    recalculatePromptTokens('txt2img_neg_prompt')
    return args_to_array(arguments);
}

function recalculate_prompts_img2img(){
    recalculatePromptTokens('img2img_prompt')
    recalculatePromptTokens('img2img_neg_prompt')
    return args_to_array(arguments);
}


opts = {}
onUiUpdate(function(){
	if(Object.keys(opts).length != 0) return;

	json_elem = gradioApp().getElementById('settings_json')
	if(json_elem == null) return;

    var textarea = json_elem.querySelector('textarea')
    var jsdata = textarea.value
    opts = JSON.parse(jsdata)
    executeCallbacks(optionsChangedCallbacks);

    Object.defineProperty(textarea, 'value', {
        set: function(newValue) {
            var valueProp = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
            var oldValue = valueProp.get.call(textarea);
            valueProp.set.call(textarea, newValue);

            if (oldValue != newValue) {
                opts = JSON.parse(textarea.value)
            }

            executeCallbacks(optionsChangedCallbacks);
        },
        get: function() {
            var valueProp = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
            return valueProp.get.call(textarea);
        }
    });

    json_elem.parentElement.style.display="none"

    function registerTextarea(id, id_counter, id_button){
        var prompt = gradioApp().getElementById(id)
        var counter = gradioApp().getElementById(id_counter)
        var textarea = gradioApp().querySelector("#" + id + " > label > textarea");

        if(counter.parentElement == prompt.parentElement){
            return
        }

        prompt.parentElement.insertBefore(counter, prompt)
        prompt.parentElement.style.position = "relative"

		promptTokecountUpdateFuncs[id] = function(){ update_token_counter(id_button); }
		textarea.addEventListener("input", promptTokecountUpdateFuncs[id]);
    }

    registerTextarea('txt2img_prompt', 'txt2img_token_counter', 'txt2img_token_button')
    registerTextarea('txt2img_neg_prompt', 'txt2img_negative_token_counter', 'txt2img_negative_token_button')
    registerTextarea('img2img_prompt', 'img2img_token_counter', 'img2img_token_button')
    registerTextarea('img2img_neg_prompt', 'img2img_negative_token_counter', 'img2img_negative_token_button')

    show_all_pages = gradioApp().getElementById('settings_show_all_pages')
    settings_tabs = gradioApp().querySelector('#settings div')
    if(show_all_pages && settings_tabs){
        settings_tabs.appendChild(show_all_pages)
        show_all_pages.onclick = function(){
            gradioApp().querySelectorAll('#settings > div').forEach(function(elem){
                elem.style.display = "block";
            })
        }
    }
})

onOptionsChanged(function(){
    elem = gradioApp().getElementById('sd_checkpoint_hash')
    sd_checkpoint_hash = opts.sd_checkpoint_hash || ""
    shorthash = sd_checkpoint_hash.substr(0,10)

	if(elem && elem.textContent != shorthash){
	    elem.textContent = shorthash
	    elem.title = sd_checkpoint_hash
	    elem.href = "https://google.com/search?q=" + sd_checkpoint_hash
	}
})

let txt2img_textarea, img2img_textarea = undefined;
let wait_time = 800
let token_timeouts = {};

function update_txt2img_tokens(...args) {
	update_token_counter("txt2img_token_button")
	if (args.length == 2)
		return args[0]
	return args;
}

function update_img2img_tokens(...args) {
	update_token_counter("img2img_token_button")
	if (args.length == 2)
		return args[0]
	return args;
}

function update_token_counter(button_id) {
	if (token_timeouts[button_id])
		clearTimeout(token_timeouts[button_id]);
	token_timeouts[button_id] = setTimeout(() => gradioApp().getElementById(button_id)?.click(), wait_time);
}

function restart_reload(){
    document.body.innerHTML='<h1 style="font-family:monospace;margin-top:20%;color:lightgray;text-align:center;">Reloading...</h1>';
    setTimeout(function(){location.reload()},2000)

    return []
}

function redirect_to_payment(need_upgrade){
    if (need_upgrade) {
        window.location.href = "/user?upgradeFlag=true";
    }
}

// Simulate an `input` DOM event for Gradio Textbox component. Needed after you edit its contents in javascript, otherwise your edits
// will only visible on web page and not sent to python.
function updateInput(target){
	let e = new Event("input", { bubbles: true })
	Object.defineProperty(e, "target", {value: target})
	target.dispatchEvent(e);
}


var desiredCheckpointName = null;
function selectCheckpoint(name){
    desiredCheckpointName = name;
    gradioApp().getElementById('change_checkpoint').click()
}

function currentImg2imgSourceResolution(_, _, scaleBy){
    var img = gradioApp().querySelector('#mode_img2img > div[style="display: block;"] img')
    return img ? [img.naturalWidth, img.naturalHeight, scaleBy] : [0, 0, scaleBy]
}

function updateImg2imgResizeToTextAfterChangingImage(){
    // At the time this is called from gradio, the image has no yet been replaced.
    // There may be a better solution, but this is simple and straightforward so I'm going with it.

    setTimeout(function() {
        gradioApp().getElementById('img2img_update_resize_to').click()
    }, 500);

    return []
}

async function browseModels(){
    var txt2img_tab = gradioApp().querySelector("#tab_txt2img");
    var img2img_tab = gradioApp().querySelector("#tab_img2img");
    var txt2img_model_refresh_button = gradioApp().querySelector('#txt2img_extra_refresh');
    var img2img_model_refresh_button = gradioApp().querySelector('#img2img_extra_refresh');

    if (txt2img_tab.style.display == "none" && img2img_tab.style.display == "none")
    {
        var txt2img_tab_button = document.querySelector("#tabs > div.tab-nav > button:nth-child(1)");
        txt2img_tab_button.click();
        await new Promise(r => setTimeout(r, 100));
    }

    var txt2img_button = gradioApp().querySelector("#txt2img_extra_networks");
    if (txt2img_tab.style.display == "block")
    {
        if (gradioApp().querySelector("div#txt2img_extra_networks").classList.contains("hide"))
        {
            fetchPageDataAndUpdateList({tabname: 'txt2img', model_type: currentTab.get('txt2img'), page: 1});
        } else {
            fetchPageDataAndUpdateList({tabname: 'txt2img', model_type: currentTab.get('txt2img'), page: 1, need_refresh: true, loading: false});
        }
        txt2img_button.click();
    }

    var img2img_button = gradioApp().querySelector("#img2img_extra_networks");
    if (img2img_tab.style.display == "block")
    {
        if (gradioApp().querySelector("div#img2img_extra_networks").classList.contains("hide"))
        {
            fetchPageDataAndUpdateList({tabname: 'img2img', model_type: currentTab.get('img2img'), page: 1});
        } else {
            fetchPageDataAndUpdateList({tabname: 'img2img', model_type: currentTab.get('img2img'), page: 1, need_refresh: true, loading: false});
        }
        img2img_button.click();
    }
}

function searchModel({model_type, searchValue}) {
    return fetch(`/sd_extra_networks/update_page?model_type=${model_type}&page=1&search_value=${searchValue}&page_size=10&need_refresh=false`, {
        method: "GET", cache: "no-cache"});
}

async function getModelFromUrl() {

    // get model form url
    const urlParam = new URLSearchParams(location.search);
    // const checkpointModelValueFromUrl = urlParam.get('checkpoint');

    // document.cookie = `selected_checkpoint_model=${checkpointModelValueFromUrl}`;
    const keyMapModelType = {
        "checkpoint": "checkpoints",
        "lora": "lora",
        "ti": "textual_inversion",
        "hn": "hypernetworks"
    }

    const promiseList = [];
    const urlList = urlParam.entries();
    const urlKeys =  [];
    const urlValues =  [];
    let checkpoint = null;

    for (const [key, value] of urlList) {
        if (keyMapModelType[key]) {
             if(key === 'checkpoint') {
                if (!checkpoint) {
                    checkpoint = value;
                    const response = searchModel({ model_type: keyMapModelType[key], searchValue: value.toLowerCase() })
                    promiseList.push(response);
                    urlKeys.push(key);
                    urlValues.push(value);
                } else {
                    notifier.alert('There are multiple checkpoint in the url, we will use the first one and discard the rest')
                }
             } else {
                const response = searchModel({ model_type: keyMapModelType[key], searchValue: value.toLowerCase() })
                promiseList.push(response);
                urlKeys.push(key);
                urlValues.push(value);
             }
        }
    }

    const allPromise = Promise.all(promiseList);

    notifier.asyncBlock(allPromise, async (promisesRes) => {
        promisesRes.forEach(async (response, index) => {
            const { model_list, allow_negative_prompt } = await response.json()
            if (model_list.length === 0) {
                notifier.alert(`${keyMapModelType[urlKeys[index]]} ${urlValues[index]} not found`, {
                    labels: {
                        alert: 'Model not Found'
                    }
                })
            } else {
                if(urlKeys[index] === 'checkpoint') {
                    selectCheckpoint(model_list[0].name)
                }
                // checkpoint dont need to replace text
                if (model_list[0].prompt) {
                    cardClicked('txt2img', eval(model_list[0].prompt), allow_negative_prompt);
                }
            }
        })
    });
    
}

function imgExists(url, imgNode, name){
    const img = new Image();
    img.src= url;
    img.onerror = () => {
        imgNode.src = `https://ui-avatars.com/api/?name=${name}&background=7F8B95&color=fff&length=1&format=svg`
    }
    img.onload = () => {
        imgNode.src = url;
    }
}

// get user info
onUiLoaded(function(){
    // update generate button text
    updateGenerateBtn_txt2img();
    updateGenerateBtn_img2img();

    getModelFromUrl();

    const {origin: hostOrigin, search} = location;
    const isDarkTheme = /theme=dark/g.test(search);
    if (isDarkTheme) {
        const rightContent = gradioApp().querySelector(".right-content");
        const discordIcon = rightContent.querySelector("div.discord-icon > a > img");
        discordIcon.style.filter = 'invert(100%)';
        const lightningIcon = rightContent.querySelector("div.upgrade-content > a > img");
        lightningIcon.style.filter = 'invert(100%)';
    }
   

    fetch(`${hostOrigin}/api/order_info`, {method: "GET", credentials: "include"}).then(res => {
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
                        const upgradeContent = userContent.querySelector(".upgrade-content");
                        if (upgradeContent) {
                            upgradeContent.style.display = 'flex';
                        }
                    }
                }
        }
    })
});
