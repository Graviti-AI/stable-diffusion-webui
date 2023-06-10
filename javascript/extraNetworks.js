
function setupExtraNetworksForTab(tabname){
    gradioApp().querySelector('#'+tabname+'_extra_tabs').classList.add('extra-networks')

    var tabs = gradioApp().querySelector('#'+tabname+'_extra_tabs > div')
    var search = gradioApp().querySelector('#'+tabname+'_extra_search textarea')
    var refresh = gradioApp().getElementById(tabname+'_extra_refresh')
    var matureLevel = gradioApp().getElementById(tabname+'_mature_level')


    search.classList.add('search')
    matureLevel.classList.add('mature_level');
    tabs.appendChild(search)
    tabs.appendChild(refresh)
    tabs.appendChild(matureLevel)

    search.addEventListener("input", function(evt){
        const model_type = currentTab.get(tabname);
        // reset page
        const currentPageTabsId = `${tabname}_${model_type}_current_page`;
        currentPageForTabs.set(currentPageTabsId, 1);

        fetchHomePageDataAndUpdateList({tabname, model_type, page: 1, loading: false});
    });
}

const activePromptTextarea = {};
let pageSize;
let homePageMatureLevel = "None";

function setupExtraNetworks(){
    setupExtraNetworksForTab('txt2img')
    setupExtraNetworksForTab('img2img')

    function registerPrompt(tabname, id){
        var textarea = gradioApp().querySelector("#" + id + " > label > textarea");

        if (! activePromptTextarea[tabname]){
            activePromptTextarea[tabname] = textarea
        }

		textarea.addEventListener("focus", function(){
            activePromptTextarea[tabname] = textarea;
		});
    }

    registerPrompt('txt2img', 'txt2img_prompt')
    registerPrompt('txt2img', 'txt2img_neg_prompt')
    registerPrompt('img2img', 'img2img_prompt')
    registerPrompt('img2img', 'img2img_neg_prompt')
}

var re_extranet   =    /<([^:]+:[^:]+):[\d\.]+>/;
var re_extranet_g = /\s+<([^:]+:[^:]+):[\d\.]+>/g;

function tryToRemoveExtraNetworkFromPrompt(textarea, text){
    var m = text.match(re_extranet)
    if(! m) return false

    var partToSearch = m[1]
    var replaced = false
    var newTextareaText = textarea.value.replaceAll(re_extranet_g, function(found, index){
        m = found.match(re_extranet);
        if(m[1] == partToSearch){
            replaced = true;
            return ""
        }
        return found;
    })

    if(replaced){
        textarea.value = newTextareaText
        return true;
    }

    return false
}

function cardClicked(tabname, textToAdd, allowNegativePrompt){
    var textarea = allowNegativePrompt ? activePromptTextarea[tabname] : gradioApp().querySelector("#" + tabname + "_prompt > label > textarea")
    if(!tryToRemoveExtraNetworkFromPrompt(textarea, textToAdd)){
        textarea.value = textarea.value + opts.extra_networks_add_text_separator + textToAdd
    }

    updateInput(textarea)
}

function saveCardPreview(event, tabname, filename){
    var textarea = gradioApp().querySelector("#" + tabname + '_preview_filename  > label > textarea')
    var button = gradioApp().getElementById(tabname + '_save_preview')

    textarea.value = filename
    updateInput(textarea)

    button.click()

    event.stopPropagation()
    event.preventDefault()
}

function extraNetworksSearchButton(tabs_id, event){
    searchTextarea = gradioApp().querySelector("#" + tabs_id + ' > div > textarea')
    button = event.target
    text = button.classList.contains("search-all") ? "" : button.textContent.trim()

    searchTextarea.value = text
    updateInput(searchTextarea)
}

var globalPopup = {
    meta: null,
    gallary: null
};
var globalPopupInner = {
    meta: null,
    gallary: null
};
function popup(contents, type){
    if(!globalPopup[type]){
        globalPopup[type] = document.createElement('div')
        globalPopup[type].onclick = function(){  globalPopup[type].style.display = "none"; };
        globalPopup[type].classList.add('global-popup');

        var close = document.createElement('div')
        close.classList.add('global-popup-close');
        close.onclick = function(){ globalPopup[type].style.display = "none"; };
        close.title = "Close";
        globalPopup[type].appendChild(close)

        globalPopupInner[type] = document.createElement('div')
        globalPopupInner[type].onclick = function(event){ event.stopPropagation(); return false; };
        globalPopupInner[type].classList.add('global-popup-inner');
        globalPopup[type].appendChild(globalPopupInner[type])

        gradioApp().appendChild(globalPopup[type]);
    }

    globalPopupInner[type].innerHTML = '';
    globalPopupInner[type].appendChild(contents);

    globalPopup[type].style.display = "flex";
}

function extraNetworksShowMetadata(text){
    elem = document.createElement('div')
    elem.classList.add('popup-metadata');
    elem.innerHTML = text;

    popup(elem, 'meta');
}

function requestGet(url, data, handler, errorHandler){
    var xhr = new XMLHttpRequest();
    var args = Object.keys(data).map(function(k){ return encodeURIComponent(k) + '=' + encodeURIComponent(data[k]) }).join('&')
    xhr.open("GET", url + "?" + args, true);

    xhr.onreadystatechange = function () {
        if (xhr.readyState === 4) {
            if (xhr.status === 200) {
                try {
                    var js = JSON.parse(xhr.responseText);
                    handler(js)
                } catch (error) {
                    console.error(error);
                    errorHandler()
                }
            } else{
                errorHandler()
            }
        }
    };
    var js = JSON.stringify(data);
    xhr.send(js);
}

async function extraNetworksRequestMetadata(event, extraPage, cardName){
    event.stopPropagation()

    showError = function(){ extraNetworksShowMetadata("<h1>there was an error getting metadata</h1>"); }

    try {
        const response = await fetch(
            `/sd_extra_networks/metadata?page=${encodeURIComponent(extraPage)}&item=${encodeURIComponent(cardName)}`,
            {method: "GET"});
        const metadata_html_str = await response.text();
        if(metadata_html_str){
            extraNetworksShowMetadata(metadata_html_str)
        } else{
            showError()
        }
    } catch (error) {
        showError()
  }
}

async function updatePrivatePreviews(tabname, model_type) {
    var cards = gradioApp().querySelectorAll(`#${tabname}_${model_type}_cards>div`);
    const response = await fetch(`/sd_extra_networks/private_previews?page_name=${model_type}`, {
        method: "GET", cache: "no-cache"});
    const private_preview_list = await response.json();
    cards.forEach((card) => {
        const filename = card.getAttribute("filename");
        if (filename) {
            private_preview_list.forEach((preview_info) => {
                if (preview_info.filename_no_extension == filename) {
                    card.style.backgroundImage = preview_info.css_url;
                }
            });
        }
    });
}

function updateTabPrivatePreviews(tabname) {
    refreshModelList({tabname})
}

const currentPageForTabs = new Map();
const totalCountForTabs = new Map();
let currentTab = new Map();
currentTab.set('txt2img', 'checkpoints');
currentTab.set('img2img', 'checkpoints');

async function handleData({response, tabname, model_type }) {
    const cardsParentNode = gradioApp().querySelector(`#${tabname}_${model_type}_cards`);
    const currentPageTabsId = `${tabname}_${model_type}_current_page`;
    const currentTotalCountId = `${tabname}_${model_type}_total_count`;
    const totalPageNode = gradioApp().querySelector(`#${tabname}_${model_type}_pagination_row .total-page`);
    const currentPageNode = gradioApp().querySelector(`#${tabname}_${model_type}_pagination_row .current-page`);
    const addModelBtnNode = cardsParentNode.querySelector(`#${tabname}_${model_type}_add_model-to-workspace`);
    const uploadBtnNode = cardsParentNode.querySelector(`#${tabname}_${model_type}_upload_button-card`);

    const { model_list, page: resPage, total_count: totalCount, allow_negative_prompt = false } = await response.json();

    // set page
    currentPageForTabs.set(currentPageTabsId, resPage || currentPage);
    currentPageNode.innerHTML = resPage || currentPage;

    // set total count
    totalCountForTabs.set(currentTotalCountId, totalCount);
    totalPageNode.innerHTML = Math.ceil(totalCount / pageSize);

    // remove child node
    const cards = cardsParentNode.querySelectorAll(".card");
    cards.forEach(card => {
        // exclude upload button
        if(card.id !== uploadBtnNode.id && card.id !== addModelBtnNode.id) {
            cardsParentNode.removeChild(card);
        }
    })

    if (model_list.length  === 0) {
        addModelBtnNode.style.display = 'block';
    } else {
        addModelBtnNode.style.display = 'none';
    }

    // add new child
    model_list.forEach(item => {
        const cardNode = document.createElement('div');
        cardNode.className = 'card';
        if (item.onclick) {
            cardNode.setAttribute('onclick', item.onclick.replaceAll(/\"/g, '').replaceAll(/&quot;/g, '"'));
        } else {
            cardNode.setAttribute('onclick', `return cardClicked('${tabname}', '${item.prompt}', ${allow_negative_prompt})`)
        }

        cardNode.setAttribute('mature-level', item.preview_mature_level || 'None');
        cardNode.setAttribute('filename', item.name);

        cardNode.innerHTML = `
            <div class="set-bg-filter"></div>
            <div class="metadata-button" title="Show metadata" onclick="extraNetworksRequestMetadata(event, '${model_type}', '${item.name}')"></div>
            <div class="actions">
                <div class="additional">
                    <ul>
                        <a title="replace preview image with currently selected in gallery" onclick="return saveCardPreview(event, '${tabname}', '${model_type}/${item.name}.png')" target="_blank">
                            set private preview
                        </a>
                    </ul>
                    <span class="search_term" style="display: none;">${item.search_term || ''}</span>
                </div>
                <span class="name">${item.name}</span>
                <span class="description"></span>
            </div>

        `
        const bgFilter = cardNode.querySelector('.set-bg-filter');
        if (item.preview) {
            bgFilter.style.backgroundImage = `url(${item.preview.replace(/\s/g, encodeURIComponent(' '))})`;
        }

        if (judgeLevel(homePageMatureLevel, cardNode.getAttribute('mature-level'))) {
            bgFilter.style['filter'] = 'blur(10px)';
        }
        cardsParentNode.insertBefore(cardNode, uploadBtnNode);
    })
}

async function fetchHomePageDataAndUpdateList({tabname, model_type, page, loading=true}) {
   const searchValue = gradioApp().querySelector('#'+tabname+'_extra_tabs textarea').value.toLowerCase();
   const requestUrl = connectNewModelApi ? `/internal/favorite_models?model_type=${model_type_mapper[model_type]}&search_value=${searchValue}&page=${page}&page_size=${pageSize}` 
        : `/sd_extra_networks/models?page_name=${model_type}&page=${page}&search_value=${searchValue}&page_size=${pageSize}&need_refresh=false`
   const promise = fetchGet(requestUrl);
    
   // loading
    if (loading) {
        notifier.asyncBlock(promise, (response) => {
            handleData({response, tabname, model_type })
        });
    } else {
        const response = await promise;
        handleData({ response, tabname, model_type })
    }
}

function updatePage(tabname, model_type, page_type) {
    let currentPage = 1;
    let totalCount;

    const currentPageTabsId = `${tabname}_${model_type}_current_page`;
    const currentTotalCountId = `${tabname}_${model_type}_total_count`;

    currentPage = currentPageForTabs.get(currentPageTabsId);
    totalCount = totalCountForTabs.get(currentTotalCountId);

    if (currentPage === 1 && page_type === 'previous') {
        return
     }
     if (currentPage * pageSize >= totalCount && page_type === 'next') {
        return
     }
    const page = page_type === 'previous' ? currentPage - 1 : currentPage + 1;
    fetchHomePageDataAndUpdateList({ tabname, model_type, page });
}

function setPageSize() {
    const contentWidth = document.body.clientWidth - 84;
    pageSize = Math.floor(contentWidth / 238) * 2;
}

async function refreshModelList({tabname}) {
    const model_type = currentTab.get(tabname);
    const currentPageTabsId = `${tabname}_${model_type}_current_page`;
    const currentPage = currentPageForTabs.get(currentPageTabsId) || 1;
    fetchHomePageDataAndUpdateList({tabname, model_type, page: currentPage, need_refresh: true});
}

function modelTabClick({tabname, model_type}) {
    let currentPage = 1;
    const currentPageTabsId = `${tabname}_${model_type}_current_page`;
    if (currentPageForTabs.has(currentPageTabsId)) {
        currentPage = currentPageForTabs.get(currentPageTabsId);
    } else {
        currentPageForTabs.set(currentPageTabsId, 1);
    }

    currentTab.set(tabname, model_type);

    fetchHomePageDataAndUpdateList({tabname, model_type, page: currentPage});
}

function changeHomeMatureLevel(selectedLevel, {tabname}) {
    const modelType = currentTab.get(tabname);
    homePageMatureLevel = selectedLevel;
    const cardList = gradioApp().querySelector(`#${tabname}_${modelType}_cards`).querySelectorAll('.card');
    cardList.forEach(card => {
        if (card.id !== `${tabname}_${modelType}_upload_button-card` && card.id !== `${tabname}_${modelType}_add_model-to-workspace`) {
            const needBlur = judgeLevel(selectedLevel, card.getAttribute('mature-level'));
            const bgFilter = card.querySelector('.set-bg-filter');
            bgFilter.style['filter'] = needBlur ? 'blur(10px)' : 'none';
        }
    })
}

onUiLoaded(function() {
    setupExtraNetworks();
    setPageSize();
});
