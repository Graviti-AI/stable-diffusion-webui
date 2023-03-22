function toggleCss(key, css, enable) {
    var style = document.getElementById(key);
    if (enable && !style) {
        style = document.createElement('style');
        style.id = key;
        style.type = 'text/css';
        document.head.appendChild(style);
    }
    if (style && !enable) {
        document.head.removeChild(style);
    }
    if (style) {
        style.innerHTML == '';
        style.appendChild(document.createTextNode(css));
    }
}

function setupExtraNetworksForTab(tabname) {
    gradioApp().querySelector('#' + tabname + '_extra_tabs').classList.add('extra-networks');

    var tabs = gradioApp().querySelector('#' + tabname + '_extra_tabs > div');
    var searchDiv = gradioApp().getElementById(tabname + '_extra_search');
    var search = searchDiv.querySelector('textarea');
    var sort = gradioApp().getElementById(tabname + '_extra_sort');
    var sortOrder = gradioApp().getElementById(tabname + '_extra_sortorder');
    var refresh = gradioApp().getElementById(tabname + '_extra_refresh');
    var matureLevel = gradioApp().getElementById(tabname+'_mature_level');

    search.classList.add('search');
    // Sort related functionalities
    sort.classList.add('sort');
    sortOrder.classList.add('sortorder');
    sort.dataset.sortkey = 'sortDefault';

    matureLevel.classList.add('mature_level');
    matureLevel.style['minWidth'] = '';

    tabs.appendChild(search);
    tabs.appendChild(sort);
    tabs.appendChild(sortOrder);
    tabs.appendChild(refresh);
    tabs.appendChild(matureLevel);

    var applyFilter = function() {
        const model_type = currentTab.get(tabname);
        // reset page
        const currentPageTabsId = `${tabname}_${model_type}_current_page`;
        currentPageForTabs.set(currentPageTabsId, 1);

        fetchHomePageDataAndUpdateList({tabname, model_type, page: 1, loading: false});
    };

    var applySort = function() {
        var reverse = sortOrder.classList.contains("sortReverse");
        var sortKey = sort.querySelector("input").value.toLowerCase().replace("sort", "").replaceAll(" ", "_").replace(/_+$/, "").trim();
        sortKey = sortKey ? "sort" + sortKey.charAt(0).toUpperCase() + sortKey.slice(1) : "";
        var sortKeyStore = sortKey ? sortKey + (reverse ? "Reverse" : "") : "";
        if (!sortKey || sortKeyStore == sort.dataset.sortkey) {
            return;
        }

        sort.dataset.sortkey = sortKeyStore;

        var cards = gradioApp().querySelectorAll('#' + tabname + '_extra_tabs div.card');
        cards.forEach(function(card) {
            card.originalParentElement = card.parentElement;
        });
        var sortedCards = Array.from(cards);
        sortedCards.sort(function(cardA, cardB) {
            var a = cardA.dataset[sortKey];
            var b = cardB.dataset[sortKey];
            if (!isNaN(a) && !isNaN(b)) {
                return parseInt(a) - parseInt(b);
            }

            return (a < b ? -1 : (a > b ? 1 : 0));
        });
        if (reverse) {
            sortedCards.reverse();
        }
        cards.forEach(function(card) {
            card.remove();
        });
        sortedCards.forEach(function(card) {
            card.originalParentElement.appendChild(card);
        });
    };

    search.addEventListener("input", applyFilter);

    //applyFilter();

    // Sort selections
    ["change", "blur", "click"].forEach(function(evt) {
        sort.querySelector("input").addEventListener(evt, applySort);
    });
    sortOrder.addEventListener("click", function() {
        sortOrder.classList.toggle("sortReverse");
        applySort();
    });

    extraNetworksApplyFilter[tabname] = applyFilter;

}

function applyExtraNetworkFilter(tabname) {
    setTimeout(extraNetworksApplyFilter[tabname], 1);
}

var extraNetworksApplyFilter = {};
var activePromptTextarea = {};
let pageSize;
let homePageMatureLevel = "None";

function setupExtraNetworks() {
    // setupExtraNetworksForTab('txt2img');
    setupExtraNetworksForTab('img2img');

    function registerPrompt(tabname, id) {
        var textarea = gradioApp().querySelector("#" + id + " > label > textarea");

        if (!activePromptTextarea[tabname]) {
            activePromptTextarea[tabname] = textarea;
        }

        textarea.addEventListener("focus", function() {
            activePromptTextarea[tabname] = textarea;
        });
    }

    registerPrompt('txt2img', 'txt2img_prompt');
    registerPrompt('txt2img', 'txt2img_neg_prompt');
    registerPrompt('img2img', 'img2img_prompt');
    registerPrompt('img2img', 'img2img_neg_prompt');
}


var re_extranet = /<([^:]+:[^:]+):[\d.]+>(.*)/;
//var re_extranet = /<([^:]+:[^:]+):[\d.]+>/;
var re_extranet_g = /\s+<([^:]+:[^:]+):[\d.]+>/g;

function tryToRemoveExtraNetworkFromPrompt(textarea, text) {
    var m = text.match(re_extranet);
    var replaced = false;
    var newTextareaText;
    if (m) {
        var extraTextAfterNet = m[2];
        var partToSearch = m[1];
        var foundAtPosition = -1;
        newTextareaText = textarea.value.replaceAll(re_extranet_g, function(found, net, pos) {
            m = found.match(re_extranet);
            if (m[1] == partToSearch) {
                replaced = true;
                foundAtPosition = pos;
                return "";
            }
            return found;
        });

        if (foundAtPosition >= 0 && newTextareaText.substr(foundAtPosition, extraTextAfterNet.length) == extraTextAfterNet) {
            newTextareaText = newTextareaText.substr(0, foundAtPosition) + newTextareaText.substr(foundAtPosition + extraTextAfterNet.length);
        }
    } else {
        newTextareaText = textarea.value.replaceAll(new RegExp(text, "g"), function(found) {
            if (found == text) {
                replaced = true;
                return "";
            }
            return found;
        });
    }

    if (replaced) {
        textarea.value = newTextareaText;
        return true;
    }

    return false;
}

function cardClicked(tabname, textToAdd, allowNegativePrompt) {
    tabname = null;
    const tab_txt2img = gradioApp().querySelector("#tab_txt2img");
    if (tab_txt2img.style.display == "block") {
      tabname = "txt2img";
    }
    const tab_img2img = gradioApp().querySelector("#tab_img2img");
    if (tab_img2img.style.display == "block") {
      tabname = "img2img";
    }
    if (tabname) {
      var textarea = allowNegativePrompt ? activePromptTextarea[tabname] : gradioApp().querySelector("#" + tabname + "_prompt > label > textarea");

      if (!tryToRemoveExtraNetworkFromPrompt(textarea, textToAdd)) {
          textarea.value = textarea.value + opts.extra_networks_add_text_separator + textToAdd;
      }

      updateInput(textarea);
    }
}

function saveCardPreview(event, tabname, filename) {
    tabname = "img2img";
    var textarea = gradioApp().querySelector("#" + tabname + '_preview_filename  > label > textarea');
    var button = gradioApp().getElementById(tabname + '_save_preview');

    textarea.value = filename;
    updateInput(textarea);

    button.click();

    event.stopPropagation();
    event.preventDefault();
}

function extraNetworksSearchButton(tabs_id, event) {
    var searchTextarea = gradioApp().querySelector("#" + tabs_id + ' > label > textarea');
    var button = event.target;
    var text = button.classList.contains("search-all") ? "" : button.textContent.trim();

    searchTextarea.value = text;
    updateInput(searchTextarea);
}

var globalPopup = {
    meta: null,
    gallary: null,
    common: null,
};
var globalPopupInner = {
    meta: null,
    gallary: null,
    common: null,
};

function closePopup(type='common') {
    if (!globalPopup[type]) return;

    globalPopup[type].style.display = "none";
}

function popup(contents, type='common') {
    if (!globalPopup[type]) {
        globalPopup[type] = document.createElement('div');
        globalPopup[type].onclick = function() {
            globalPopup[type].style.display = "none";
        };
        globalPopup[type].classList.add('global-popup');

        var close = document.createElement('div');
        close.classList.add('global-popup-close');
        close.onclick = function() {
            globalPopup[type].style.display = "none";
        };
        close.title = "Close";
        globalPopup[type].appendChild(close);

        globalPopupInner[type] = document.createElement('div');
        globalPopupInner[type].onclick = function(event) {
            event.stopPropagation(); return false;
        };
        globalPopupInner[type].classList.add('global-popup-inner');
        globalPopup[type].appendChild(globalPopupInner[type]);

        gradioApp().querySelector('.main').appendChild(globalPopup[type]);
        //gradioApp().appendChild(globalPopup[type]);
    }

    globalPopupInner[type].innerHTML = '';
    globalPopupInner[type].appendChild(contents);

    globalPopup[type].style.display = "flex";
}

var storedPopupIds = {};
function popupId(id, type='common') {
    if (!storedPopupIds[id]) {
        storedPopupIds[id] = gradioApp().getElementById(id);
    }

    popup(storedPopupIds[id], type);
}

function extraNetworksShowMetadata(text) {
    var elem = document.createElement('div');
    elem.classList.add('popup-metadata');
    elem.innerHTML = text;

    popup(elem, 'meta');
}

function requestGet(url, data, handler, errorHandler) {
    var xhr = new XMLHttpRequest();
    var args = Object.keys(data).map(function(k) {
        return encodeURIComponent(k) + '=' + encodeURIComponent(data[k]);
    }).join('&');
    xhr.open("GET", url + "?" + args, true);

    xhr.onreadystatechange = function() {
        if (xhr.readyState === 4) {
            if (xhr.status === 200) {
                try {
                    var js = JSON.parse(xhr.responseText);
                    handler(js);
                } catch (error) {
                    console.error(error);
                    errorHandler();
                }
            } else {
                errorHandler();
            }
        }
    };
    var js = JSON.stringify(data);
    xhr.send(js);
}

async function extraNetworksRequestMetadata(event, extraPage, cardName) {
    event.stopPropagation()

    var showError = function(){ extraNetworksShowMetadata("<h1>there was an error getting metadata</h1>"); }

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

var extraPageUserMetadataEditors = {};

function extraNetworksEditUserMetadata(event, tabname, extraPage, cardName) {
    var id = tabname + '_' + extraPage + '_edit_user_metadata';

    var editor = extraPageUserMetadataEditors[id];
    if (!editor) {
        editor = {};
        editor.page = gradioApp().getElementById(id);
        editor.nameTextarea = gradioApp().querySelector("#" + id + "_name" + ' textarea');
        editor.button = gradioApp().querySelector("#" + id + "_button");
        extraPageUserMetadataEditors[id] = editor;
    }

    editor.nameTextarea.value = cardName;
    updateInput(editor.nameTextarea);

    editor.button.click();

    popup(editor.page);

    event.stopPropagation();
}

function extraNetworksRefreshSingleCard(page, tabname, name) {
    requestGet("./sd_extra_networks/get-single-card", {page: page, tabname: tabname, name: name}, function(data) {
        if (data && data.html) {
            var card = gradioApp().querySelector('.card[data-name=' + JSON.stringify(name) + ']'); // likely using the wrong stringify function

            var newDiv = document.createElement('DIV');
            newDiv.innerHTML = data.html;
            var newCard = newDiv.firstElementChild;

            newCard.style.display = '';
            card.parentElement.insertBefore(newCard, card);
            card.parentElement.removeChild(card);
        }
    });
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
    const uploadPrivateBtnNode = cardsParentNode.querySelector(`#${tabname}_${model_type}_upload_button-card-private`);
    const currentPage = currentPageForTabs.get(currentPageTabsId) || 1;

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
        if (
            card.id !== uploadBtnNode.id &&
            card.id !== addModelBtnNode.id &&
            card.id !== uploadPrivateBtnNode.id
        ) {
            cardsParentNode.removeChild(card);
        }
    })

    if (model_list && model_list.length === 0) {
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
            cardNode.setAttribute('onclick', `return cardClicked('${tabname}', ${item.prompt}, ${allow_negative_prompt})`)
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
                <span class="name">${item.name_for_extra}</span>
                <span class="description"></span>
            </div>

        `
        const bgFilter = cardNode.querySelector('.set-bg-filter');
        if (item.preview) {
            bgFilter.style.backgroundImage = `url('${item.preview.replace(/\s/g, encodeURIComponent(' '))}')`;
        }

        if (judgeLevel(homePageMatureLevel, cardNode.getAttribute('mature-level'))) {
            bgFilter.style['filter'] = 'blur(10px)';
        }
        cardsParentNode.insertBefore(cardNode, uploadBtnNode);
    })
}

async function fetchHomePageDataAndUpdateList({tabname, model_type, page, loading=true}) {
  tabname = "img2img";
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
    setPageSize();
    setupExtraNetworks();
});
