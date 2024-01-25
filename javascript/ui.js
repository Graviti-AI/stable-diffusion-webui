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

async function _getFeaturePermissions() {
    if (!featurePermissions) {
        const response = await fetchGet("/config/feature_permissions");
        const body = await response.json()
        featurePermissions = {
            generate: body.generate,
            buttons: Object.fromEntries(body.buttons.map((item) => [item.name, item]))
        }
    }
    return featurePermissions;

}

function _joinWords(words, conjunction = "and") {
    const names = words.map((item) => `"${item}"`);
    if (names.length == 1) {
        return names[0];
    }
    const last_name = names.pop();
    return `${names.join(", ")} ${conjunction} ${last_name}`;
}

function _joinTiers(tiers) {
    const unique_tiers = [];
    for (let tier of ["Basic", "Plus", "Pro", "Api"]) {
        if (tiers.includes(tier)) {
            unique_tiers.push(tier);
        }
    }
    return _joinWords(unique_tiers, "or");
}

function _tierCheckFailed(features, allowed_tiers) {
    notifier.confirm(
        `${features} is not available in the current plan. Please upgrade to ${allowed_tiers} to use it.`,
        () => {
            addUpgradeGtagEvent(SUBSCRIPTION_URL, "tier_checker");
            window.open(SUBSCRIPTION_URL, "_blank");
        },
        () => {},
        {
            labels: {
                confirm: 'Upgrade Now',
                confirmOk: 'Upgrade'
            }
        }
    );
    throw `${features} is not available for current tier.`;
}

async function tierCheckGenerate(tabname) {
    const features = [];
    const allowed_tiers = [];
    let is_order_info_requested = false;

    const permissions = await _getFeaturePermissions()
    for (let permission of permissions.generate) {
        if (permission.allowed_tiers.includes(userTier)) {
            continue;
        }
        if (!is_order_info_requested) {
            await updateOrderInfo();
            is_order_info_requested = true;
            if (permission.allowed_tiers.includes(userTier)) {
                continue;
            }
        }

        const elem_id = permission[`${tabname}_id`];
        const tab_elem_id = `tab_${tabname}`
        if (permission.type === "checkbox") {
            const target_elem = document.querySelector(`#${tab_elem_id} #${elem_id} input`);
            if (target_elem.checked === permission.value) {
                continue;
            }
        } else if (permission.type === "dropdown") {
            const target_elem = document.querySelector(`#${tab_elem_id} #${elem_id} input`);
            if (target_elem.value === permission.value) {
                continue;
            }
        } else {
            continue;
        }
        features.push(permission.name);
        allowed_tiers.push(...permission.allowed_tiers);
    }

    if (features.length == 0) {
        return;
    }
    _tierCheckFailed(_joinWords(features), _joinTiers(allowed_tiers));
}


async function tierCheckButtonInternal(feature_name) {
    const permissions = await _getFeaturePermissions()
    const permission = permissions.buttons[feature_name];

    if (permission.allowed_tiers.includes(userTier)) {
        return;
    }
    await updateOrderInfo();
    if (permission.allowed_tiers.includes(userTier)) {
        return;
    }
    _tierCheckFailed(`"${feature_name}"`, _joinTiers(permission.allowed_tiers));
}

function tierCheckButton(feature_name) {
    return async (...args) => {
        await tierCheckButtonInternal(feature_name);
        return args;
    }
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

async function submit() {
    addGenerateGtagEvent("#txt2img_generate > span", "txt2img_generation_button");
    await tierCheckGenerate("txt2img");
    checkSignatureCompatibility();

    var res = create_submit_args(arguments);
    const [index, all_model_info] = await getAllModelInfo("txt2img", res);

    showSubmitButtons('txt2img', false);

    var id = randomId();
    localSet("txt2img_task_id", id);

    requestProgress(id, gradioApp().getElementById('txt2img_gallery_container'), gradioApp().getElementById('txt2img_gallery'), function() {
        showSubmitButtons('txt2img', true);
        localRemove("txt2img_task_id");
        showRestoreProgressButton('txt2img', false);
    });

    res[0] = id;
    res[index] = all_model_info;

    return res;
}

async function submit_img2img() {
    addGenerateGtagEvent("#img2img_generate > span", "img2img_generation_button");
    await tierCheckGenerate("img2img");
    showSubmitButtons('img2img', false);

    var res = create_submit_args(arguments);
    const [index, all_model_info] = await getAllModelInfo("img2img", res);

    var id = randomId();
    localSet("img2img_task_id", id);

    requestProgress(id, gradioApp().getElementById('img2img_gallery_container'), gradioApp().getElementById('img2img_gallery'), function() {
        showSubmitButtons('img2img', true);
        localRemove("img2img_task_id");
        showRestoreProgressButton('img2img', false);
    });


    res[0] = id;
    res[1] = get_tab_index('mode_img2img');
    res[index] = all_model_info;

    return res;
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

onUiLoaded(function() {
    showRestoreProgressButton('txt2img', localGet("txt2img_task_id"));
    showRestoreProgressButton('img2img', localGet("img2img_task_id"));
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

function check_nsfw(obj, boxId) {
    if (!obj.is_nsfw) {
        return;
    }
    notifier.confirm(
        `Potential NSFW content was detected in the generated image, upgrade to enable your private image storage.`,
        () => {
            addUpgradeGtagEvent(SUBSCRIPTION_URL, "nsfw_checker");
            update_textbox_by_id(boxId, "");
            window.open(SUBSCRIPTION_URL, "_blank");
        },
        () => {
            update_textbox_by_id(boxId, "");
        },
        {
            labels: {
                confirm: 'Upgrade Now',
                confirmOk: 'Upgrade'
            }
        }
    );
}

function update_textbox_by_id(id, value) {
    const box = gradioApp().querySelector(`#${id} textarea`);
    if (box) {
      box.value = value;
      updateInput(box);
    }
}

function redirect_to_payment_factory(boxId) {
  function redirect_to_payment(need_upgrade){
      if (need_upgrade) {
          const need_upgrade_obj = JSON.parse(need_upgrade);
          check_nsfw(need_upgrade_obj, boxId);
          if (need_upgrade_obj.hasOwnProperty("need_upgrade") && need_upgrade_obj.need_upgrade) {
              const message = need_upgrade_obj.hasOwnProperty("message")? need_upgrade_obj.message: "Upgrade to unlock more credits.";
              let onOk = () => {
                addUpgradeGtagEvent(SUBSCRIPTION_URL, "insufficient_credits");
                update_textbox_by_id(boxId, "");
                window.open(SUBSCRIPTION_URL, "_blank");
              };
              let onCancel = () => {
                update_textbox_by_id(boxId, "");
              };
              notifier.confirm(
                message,
                onOk,
                onCancel,
                {
                  labels: {
                    confirm: 'Upgrade Now',
                    confirmOk: 'Upgrade'
                  }
                }
              );
          }
      }
  }
  return redirect_to_payment;
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
    const browseModelsBtn = gradioApp().querySelector('#browse_models_in_workspace');
    if (gradioApp().querySelector("div#img2img_extra_networks").classList.contains("hide")) {
        browseModelsBtn.textContent = 'Hide workspace models';
    } else {
        browseModelsBtn.textContent = 'Show workspace models';
    }

    fetchHomePageDataAndUpdateList({tabname: 'img2img', model_type: currentTab.get('img2img'), page: 1});
}

async function browseModels(){
    fetchHomePageDataAndUpdateList({tabname: 'img2img', model_type: currentTab.get('img2img'), page: 1});
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
        "lycoris": "lora",
        "y": "lora",
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

function observeModalClose(modalElement, onClosedCallback) {
  let observer = new MutationObserver(function(mutations) {
    // check for removed target
    mutations.forEach(function(mutation) {
      let nodes = Array.from(mutation.removedNodes);
      let directMatch = nodes.indexOf(modalElement) > -1
      let parentMatch = nodes.some(parent => parent.contains(modalElement));
      if (directMatch) {
        if (typeof onClosedCallback === 'function') {
          onClosedCallback(modalElement);
        }
        observer.disconnect();
      } else if (parentMatch) {
        if (typeof onClosedCallback === 'function') {
          onClosedCallback(modalElement);
        }
        observer.disconnect();
      }
    });
  });

  let config = {
    subtree: true,
    childList: true
  };
  observer.observe(document.body, config);
}

function showNotification(userName, avatarUrl, closeCallback=null) {
  fetch(
    '/webui/notification?' + new URLSearchParams({
        avatar_url: avatarUrl,
        user_name: userName,
    }),
    {
      method: 'GET',
      credentials: 'include',
    }
  )
  .then(response => {
    if (response.status === 200) {
      return response.json();
    }
    return Promise.reject(response);
  })
  .then((data) => {
    if (data && data.show) {
      let doc = document.implementation.createHTMLDocument();
      doc.body.innerHTML = data.html;
      let arrayScripts = [].map.call(doc.getElementsByTagName('script'), function(el) {
        return el;
      });
      for (const index in arrayScripts) {
        doc.body.removeChild(arrayScripts[index]);
      }
      const modal = notifier.modal(doc.body.innerHTML);
      for (const index in arrayScripts) {
        let new_script = document.createElement("script");
        if (arrayScripts[index].src) {
            new_script.src = arrayScripts[index].src;
        } else {
            new_script.innerHTML = arrayScripts[index].innerHTML;
        }
        document.body.appendChild(new_script);
      }
      if (typeof closeCallback === 'function') {
        observeModalClose(modal.newNode, closeCallback);
      }
    } else {
      if (typeof closeCallback === 'function') {
        closeCallback();
      }
    }
  })
  .catch((error) => {
      console.error('Notification error:', error);
      if (typeof closeCallback === 'function') {
        closeCallback();
      }
  });
}

var notificationShowed = false;

function callShowNotification() {
  if (!notificationShowed) {
    notificationShowed = true;
    const userName = getCurrentUserName();
    const userAvatarUrl = getCurrentUserAvatar();

    showNotification(userName, userAvatarUrl, executeNotificationCallbacks);
  }
}function imgExists(url, imgNode, name){
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

    txt2imgSignaturePromise
    .then(response => {
        if (response.status === 200) {
            return response.json();
        }
        return Promise.reject(response);
    })
    .then((txt2imgSignature) => {
        if (txt2imgSignature && txt2imgSignature.signature && txt2imgSignature.fn_index) {
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

function preloadImage(url, onloadCallback, onerrorCallback)
{
    let img = new Image();
    img.src = url;
    img.onload = onloadCallback;
    img.onerror = onerrorCallback;
}

const loadImages = (htmlResponse) => new Promise((resolve, reject) => {
    let doc = document.implementation.createHTMLDocument();
    doc.body.innerHTML = htmlResponse;
    const imgs = doc.body.querySelectorAll("img");
    const totalNumImages = imgs.length;
    let imageCount = 0;

    const imageLoadCallback = () => {
        imageCount += 1;
        if (imageCount == totalNumImages) {
            resolve(doc);
        }
    }
    const onerrorCallback = (error) => {reject(error);}
    imgs.forEach(elem => {
        preloadImage(elem.src, imageLoadCallback, onerrorCallback);
    });
});

function renderInPopup(doc, onClosedCallback=null) {
    let arrayScripts = [].map.call(doc.getElementsByTagName('script'), function(el) {
        return el;
    });
    for (const index in arrayScripts) {
        doc.body.removeChild(arrayScripts[index]);
    }
    const modal =notifier.modal(doc.body.innerHTML);
    for (const index in arrayScripts) {
        let new_script = document.createElement("script");
        if (arrayScripts[index].src) {
            new_script.src = arrayScripts[index].src;
        } else {
            new_script.innerHTML = arrayScripts[index].innerHTML;
        }
        document.body.appendChild(new_script);
    }window.openningAnotherModal = false;
    if (typeof onClosedCallback === 'function') {
      observeModalClose(modal.newNode, onClosedCallback);
    }
}

function popupHtmlResponse(htmlResponse, onClosedCallback=null) {
    loadImages(htmlResponse)
    .then((doc) => {
        renderInPopup(doc, onClosedCallback);
    })
    .catch((error) => {
      console.error("Error:", error);
      window.openningAnotherModal = false;
      if (typeof onClosedCallback === 'function') {
        onClosedCallback();
      }
    });
}

function showInspirationPopup() {
    if (typeof posthog === 'object') {
      posthog.capture('Inspiration button clicked.');
    }
    let loadPromise =new Promise((resolve, reject) => {
      fetch('/inspire/html', {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json'
          },
          body: JSON.stringify({
          })
      })
      .then(response => {
          if (response.status === 200) {
              return response.text();
          }
          return Promise.reject(response);
      })
      .then(htmlResponse => {
          loadImages(htmlResponse)
          .then((doc) => {resolve(doc)})
          .catch((error) => {reject(error)});
      })
      .catch((error) => {reject(error)});
    });
    notifier.async(
      loadPromise,
      (doc) => {renderInPopup(doc);},
      (error) => {console.error('Error:', error);},
      "Selecting a good piece for you!"
    );
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
        .then((data) => {
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
                .then((htmlResponse) => {popupHtmlResponse(htmlResponse, (modalElement) => {
                  const elementWithSameId = document.getElementById(modalElement.id);
                  if (!window.openningAnotherModal && !elementWithSameId) {callShowNotification();}
                });})
                .catch((error) => {
                    console.error('Error:', error);
                window.openningAnotherModal = false;
                    callShowNotification();
                });
            } else {
              window.openningAnotherModal = false;
              callShowNotification();
            }
        })
        .catch((error) => {
            console.error('Error:', error);
        window.openningAnotherModal = false;
          callShowNotification();
        });
    } else {
      callShowNotification();
    }
}

function renderHtmlResponse(elem, url, method, onSucceeded=null, onFailed=null, body = null) {
  let fetchParams = {
    method: method.toUpperCase(),
    redirect: 'error'
  };
  if (method.toLowerCase() === 'post' && body) {
    fetchParams.headers = {
        'Content-Type': 'application/json'
    };
    fetchParams.body = JSON.stringify(body);
  }
  fetch(url, fetchParams)
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
    elem.innerHTML = doc.body.innerHTML;
    for (const index in arrayScripts) {
        let new_script = document.createElement("script");
        if (arrayScripts[index].src) {
            new_script.src = arrayScripts[index].src;
        } else {
            new_script.innerHTML = arrayScripts[index].innerHTML;
        }
        document.body.appendChild(new_script);
    }
    if (onSucceeded && typeof onSucceeded === "function") {
      onSucceeded(elem);
    }
  })
  .catch((error) => {
    console.error('Error:', error);
    if (onFailed && typeof onFailed === "function") {
      onFailed(elem, error);
    }
  });
}

var openningAnotherModal = false;

async function joinShareGroup(userName=null, avatarUrl=null) {
    const urlParams = new URLSearchParams(window.location.search);
    const share_id = urlParams.get('share_id');

    if (share_id) {
      joinShareGroupWithId(share_id, userName, avatarUrl);
    } else {
      notifyUserTheShareCampaign(userName, avatarUrl);
    }
}

function notifyUserTheShareCampaign(userName, avatarUrl) {
    const showed = window.Cookies.get("_1000by1000showed");
    if (!showed) {
        if (!userName) {
            userName = getCurrentUserName();
        }
        if (!avatarUrl) {
            avatarUrl = getCurrentUserAvatar();
        }
        fetch('/share/group/create/html', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ avatar_url: avatarUrl, user_name: userName })
        })
        .then(response => {
            if (response.status === 200) {
                return response.text();
            }
            return Promise.reject(response);
        })
        .then((data) => {
            let doc = document.implementation.createHTMLDocument();
            doc.body.innerHTML = data;
            let arrayScripts = [].map.call(doc.getElementsByTagName('script'), function(el) {
                return el;
            });
            for (const index in arrayScripts) {
                doc.body.removeChild(arrayScripts[index]);
            }
            const shareButton = doc.body.querySelector("button.share-group-share-btn");
            const checkStatusButton = doc.body.querySelector("button.share-group-status-btn");
            if (shareButton || checkStatusButton) {
                const modal =notifier.modal(doc.body.innerHTML);
                for (const index in arrayScripts) {
                    let new_script = document.createElement("script");
                    if (arrayScripts[index].src) {
                        new_script.src = arrayScripts[index].src;
                    } else {
                        new_script.innerHTML = arrayScripts[index].innerHTML;
                    }
                    document.body.appendChild(new_script);
                }
                window.Cookies.set("_1000by1000showed", true, { expires: 28 });
            observeModalClose(modal.newNode, (modalElement) => {
                  const elementWithSameId = document.getElementById(modalElement.id);
                  if (!window.openningAnotherModal && !elementWithSameId) {callShowNotification();}});
            } else {
              callShowNotification();}
        })
        .catch((error) => {
            console.error('Error:', error);
        callShowNotification();
        });
    } else {
      callShowNotification();
    }
}

function on_sd_model_selection_updated(model_title){
    return [model_title, model_title]
}


async function updateOrderInfo() {
    await fetch(`/api/order_info`, { method: "GET", credentials: "include" })
        .then((res) => {
            if (res && res.ok && !res.redirected) {
                return res.json();
            }
        })
        .then((result) => {
            if (result) {
                const userContent = gradioApp().querySelector(".user-content");
                const userInfo = userContent.querySelector(".user_info");
                if (userInfo) {
                    userTier = result.tier;
                    orderInfoResult = result;
                    userInfo.style.display = "flex";
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
                        logOutLink.target = "_self";
                        // remove cookie
                        logOutLink.onclick = () => {
                            document.cookie = "auth-session=;";
                        };
                    }

                    if (result.tier.toLowerCase() === "free") {
                        const upgradeContent = userContent.querySelector("#upgrade");
                        if (upgradeContent) {
                            upgradeContent.style.display = "flex";
                            const linkNode = upgradeContent.querySelector("a");
                            if (linkNode && linkNode.href) {
                              linkNode.addEventListener('click', (e) => {
                                e.preventDefault();
                                gtag("event", "begin_checkout", {
                                  items: [{
                                    item_id: linkNode.href,
                                    item_name: "free user webui upgrade link"
                                  }],
                                  event_callback: function () {
                                    window.location.href = linkNode.href;
                                  }
                                });
                              });
                            }
                        }
                    }
                    changeFreeCreditLink();
                    changeCreditsPackageLink();
                }
                const boostButton = gradioApp().querySelector("#one_click_boost_button");
                let onSucceededCallback = (elem) => {
                    elem.style.display = "flex";
                };
                if (boostButton) {
                    renderHtmlResponse(
                        boostButton,
                        "/boost_button/html",
                        "GET",
                        (onSucceeded = onSucceededCallback),
                    );
                }
            }
        });
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
    Cookies.set('theme', isDarkTheme ? 'dark' : 'light');
    if (isDarkTheme) {
        const rightContent = gradioApp().querySelector(".right-content");
        const imgNodes = rightContent.querySelectorAll("a > img");
        imgNodes.forEach(item => {
            item.style.filter = 'invert(100%)';
        })
    }

    setTimeout(monitorSignatureChange, 30000);
    pullNewSubscribers();
    updateOrderInfo();
});
