
function setupExtraNetworksForTab(tabname){
    gradioApp().querySelector('#'+tabname+'_extra_tabs').classList.add('extra-networks')

    var tabs = gradioApp().querySelector('#'+tabname+'_extra_tabs > div')
    var search = gradioApp().querySelector('#'+tabname+'_extra_search textarea')
    var refresh = gradioApp().getElementById(tabname+'_extra_refresh')

    search.classList.add('search')
    tabs.appendChild(search)
    tabs.appendChild(refresh)

    search.addEventListener("input", function(evt){
        const page_name = currentTab.get(tabname);
        // reset page
        const currentPageTabsId = `${tabname}_${page_name}_current_page`;
        currentPageForTabs.set(currentPageTabsId, 1);

        fetchPageDataAndUpdateList({tabname, page_name, page: 1, loading: false});
    });
}

var activePromptTextarea = {};
let pageSize;

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

async function updatePrivatePreviews(tabname, page_name) {
    var cards = gradioApp().querySelectorAll(`#${tabname}_${page_name}_cards>div`);
    const response = await fetch(`/sd_extra_networks/private_previews?page_name=${page_name}`, {
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

async function handleData({response, tabname, page_name }) {
    const cardsParentNode = gradioApp().querySelector(`#${tabname}_${page_name}_cards`);
    const currentPageTabsId = `${tabname}_${page_name}_current_page`;
    const currentTotalCountId = `${tabname}_${page_name}_total_count`;
    const totalPageNode = gradioApp().querySelector(`#${tabname}_${page_name}_pagination_row .total-page`);
    const currentPageNode = gradioApp().querySelector(`#${tabname}_${page_name}_pagination_row .current-page`);
    const addModelBtnNode = cardsParentNode.querySelector(`#${tabname}_${page_name}_add_model-to-workspace`);
    const uploadBtnNode = cardsParentNode.querySelector(`#${tabname}_${page_name}_upload_button-card`);

    const { model_list, page: resPage, total_count: totalCount, allow_negative_prompt } = await response.json();

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
            cardNode.setAttribute('onclick', `return cardClicked('${tabname}', ${item.prompt}), ${allow_negative_prompt}`)
        }

        cardNode.setAttribute('filename', item.name);
        if (item.preview) {
            cardNode.style.backgroundImage = `url(${item.preview.replace(/\s/g, encodeURIComponent(' '))})`;
        }

        const metaDataButtonNode = document.createElement('div');
        metaDataButtonNode.className = 'metadata-button';
        metaDataButtonNode.title = "Show metadata";
        metaDataButtonNode.setAttribute('onclick', `extraNetworksRequestMetadata(event, "${page_name}", "${item.name}")`);

        const actionsNode = document.createElement('div');
        actionsNode.className = 'actions';

        const additionalNode = document.createElement('div');
        additionalNode.className = "additional";

        const ulNode = document.createElement('ul');
        const aNode = document.createElement('a');
        aNode.title = "replace preview image with currently selected in gallery";
        aNode.setAttribute('onclick', `return saveCardPreview(event, "${tabname}", "${page_name}/${item.name}.png")`);
        aNode.target = "_blank";
        aNode.innerHTML = "set private preview";

        ulNode.appendChild(aNode);

        const searchTermNode = document.createElement('span');
        searchTermNode.className = "search_term";
        searchTermNode.style.display = "none";
        searchTermNode.innerHTML = item.search_term;

        const nameNode = document.createElement('span');
        nameNode.className = "name";
        nameNode.innerHTML = item.name_for_extra;

        const descriptionNode = document.createElement('span');
        descriptionNode.className = "description";

        additionalNode.appendChild(ulNode);
        additionalNode.appendChild(searchTermNode);

        actionsNode.appendChild(additionalNode);
        actionsNode.appendChild(nameNode);
        actionsNode.appendChild(descriptionNode);

        cardNode.appendChild(metaDataButtonNode);
        cardNode.appendChild(actionsNode);
        cardsParentNode.insertBefore(cardNode, uploadBtnNode);
    })
}

async function fetchPageDataAndUpdateList({tabname, page_name, page, loading=true}) {
   const searchValue = gradioApp().querySelector('#'+tabname+'_extra_tabs textarea').value.toLowerCase();
   const requestUrl = connectNewModelApi ? `/internal/favorite_models?model_type=${model_type_mapper[page_name]}&search_value=${searchValue}&page=${page}&page_size=${pageSize}` 
        : `/sd_extra_networks/models?page_name=${page_name}&page=${page}&search_value=${searchValue}&page_size=${pageSize}&need_refresh=false`
   const promise = fetchGet(requestUrl);
    
   // loading
    if (loading) {
        notifier.asyncBlock(promise, (response) => {
            handleData({response, tabname, page_name })
        });
    } else {
        const response = await promise;
        handleData({ response, tabname, page_name })
    }
}

function updatePage(tabname, page_name, page_type) {
    let currentPage = 1;
    let totalCount;

    const currentPageTabsId = `${tabname}_${page_name}_current_page`;
    const currentTotalCountId = `${tabname}_${page_name}_total_count`;

    currentPage = currentPageForTabs.get(currentPageTabsId);
    totalCount = totalCountForTabs.get(currentTotalCountId);

    if (currentPage === 1 && page_type === 'previous') {
        return
     }
     if (currentPage * pageSize >= totalCount && page_type === 'next') {
        return
     }
    const page = page_type === 'previous' ? currentPage - 1 : currentPage + 1;
    fetchPageDataAndUpdateList({ tabname, page_name, page });
}

function setPageSize() {
    const contentWidth = document.body.clientWidth - 84;
    pageSize = Math.floor(contentWidth / 238) * 2;
}

async function refreshModelList({tabname}) {
    const page_name = currentTab.get(tabname);
    const currentPageTabsId = `${tabname}_${page_name}_current_page`;
    const currentPage = currentPageForTabs.get(currentPageTabsId) || 1;
    fetchPageDataAndUpdateList({tabname, page_name, page: currentPage, need_refresh: true});
}

function modelTabClick({tabname, page_name}) {
    let currentPage = 1;
    const currentPageTabsId = `${tabname}_${page_name}_current_page`;
    if (currentPageForTabs.has(currentPageTabsId)) {
        currentPage = currentPageForTabs.get(currentPageTabsId);
    } else {
        currentPageForTabs.set(currentPageTabsId, 1);
    }

    currentTab.set(tabname, page_name);

    fetchPageDataAndUpdateList({tabname, page_name, page: currentPage});
}

onUiLoaded(function() {
    setupExtraNetworks();
    setPageSize();
});
