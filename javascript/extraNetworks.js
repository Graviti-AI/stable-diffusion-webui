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
    function registerPrompt(tabname, id) {
        var textarea = gradioApp().querySelector("#" + id + " > label > textarea");

        if (!activePromptTextarea[tabname]) {
            activePromptTextarea[tabname] = textarea;
        }

        textarea.addEventListener("focus", function() {
            activePromptTextarea[tabname] = textarea;
        });
    }

    var tabnav = gradioApp().querySelector('#' + tabname + '_extra_tabs > div.tab-nav');
    var controlsDiv = document.createElement('DIV');
    controlsDiv.classList.add('extra-networks-controls-div');
    tabnav.appendChild(controlsDiv);
    tabnav.insertBefore(controlsDiv, null);

    var this_tab = gradioApp().querySelector('#' + tabname + '_extra_tabs');
    this_tab.querySelectorAll(":scope > [id^='" + tabname + "_']").forEach(function(elem) {
        // tabname_full = {tabname}_{extra_networks_tabname}
        var tabname_full = elem.id;
        var search = gradioApp().querySelector("#" + tabname_full + "_extra_search");
        var sort_mode = gradioApp().querySelector("#" + tabname_full + "_extra_sort");
        var sort_dir = gradioApp().querySelector("#" + tabname_full + "_extra_sort_dir");
        var refresh = gradioApp().querySelector("#" + tabname_full + "_extra_refresh");

        // If any of the buttons above don't exist, we want to skip this iteration of the loop.
        if (!search || !sort_mode || !sort_dir || !refresh) {
            return; // `return` is equivalent of `continue` but for forEach loops.
        }

        var applyFilter = function(force) {
            var searchTerm = search.value.toLowerCase();
            gradioApp().querySelectorAll('#' + tabname + '_extra_tabs div.card').forEach(function(elem) {
                var searchOnly = elem.querySelector('.search_only');
                var text = Array.prototype.map.call(elem.querySelectorAll('.search_terms'), function(t) {
                    return t.textContent.toLowerCase();
                }).join(" ");

                var visible = text.indexOf(searchTerm) != -1;
                if (searchOnly && searchTerm.length < 4) {
                    visible = false;
                }
                if (visible) {
                    elem.classList.remove("hidden");
                } else {
                    elem.classList.add("hidden");
                }
            });

            applySort(force);
        };

        var applySort = function(force) {
            var cards = gradioApp().querySelectorAll('#' + tabname + '_extra_tabs div.card');
            var reverse = sort_dir.dataset.sortdir == "Descending";
            var sortKey = sort_mode.dataset.sortmode.toLowerCase().replace("sort", "").replaceAll(" ", "_").replace(/_+$/, "").trim() || "name";
            sortKey = "sort" + sortKey.charAt(0).toUpperCase() + sortKey.slice(1);
            var sortKeyStore = sortKey + "-" + (reverse ? "Descending" : "Ascending") + "-" + cards.length;

            if (sortKeyStore == sort_mode.dataset.sortkey && !force) {
                return;
            }
            sort_mode.dataset.sortkey = sortKeyStore;

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
        applySort();
        applyFilter();
        extraNetworksApplySort[tabname_full] = applySort;
        extraNetworksApplyFilter[tabname_full] = applyFilter;

        var controls = gradioApp().querySelector("#" + tabname_full + "_controls");
        controlsDiv.insertBefore(controls, null);

        if (elem.style.display != "none") {
            extraNetworksShowControlsForPage(tabname, tabname_full);
        }
    });

    registerPrompt(tabname, tabname + "_prompt");
    registerPrompt(tabname, tabname + "_neg_prompt");
}

function extraNetworksMovePromptToTab(tabname, id, showPrompt, showNegativePrompt) {
    if (!gradioApp().querySelector('.toprow-compact-tools')) return; // only applicable for compact prompt layout

    var promptContainer = gradioApp().getElementById(tabname + '_prompt_container');
    var prompt = gradioApp().getElementById(tabname + '_prompt_row');
    var negPrompt = gradioApp().getElementById(tabname + '_neg_prompt_row');
    var elem = id ? gradioApp().getElementById(id) : null;

    if (showNegativePrompt && elem) {
        elem.insertBefore(negPrompt, elem.firstChild);
    } else {
        promptContainer.insertBefore(negPrompt, promptContainer.firstChild);
    }

    if (showPrompt && elem) {
        elem.insertBefore(prompt, elem.firstChild);
    } else {
        promptContainer.insertBefore(prompt, promptContainer.firstChild);
    }

    if (elem) {
        elem.classList.toggle('extra-page-prompts-active', showNegativePrompt || showPrompt);
    }
}


function extraNetworksShowControlsForPage(tabname, tabname_full) {
    gradioApp().querySelectorAll('#' + tabname + '_extra_tabs .extra-networks-controls-div > div').forEach(function(elem) {
        var targetId = tabname_full + "_controls";
        elem.style.display = elem.id == targetId ? "" : "none";
    });
}


function extraNetworksUnrelatedTabSelected(tabname) { // called from python when user selects an unrelated tab (generate)
    extraNetworksMovePromptToTab(tabname, '', false, false);

    extraNetworksShowControlsForPage(tabname, null);
}

function extraNetworksTabSelected(tabname, id, showPrompt, showNegativePrompt, tabname_full) { // called from python when user selects an extra networks tab
    extraNetworksMovePromptToTab(tabname, id, showPrompt, showNegativePrompt);

    extraNetworksShowControlsForPage(tabname, tabname_full);
}

function applyExtraNetworkFilter(tabname_full) {
    var doFilter = function() {
        var applyFunction = extraNetworksApplyFilter[tabname_full];

        if (applyFunction) {
            applyFunction(true);
        }
    };
    setTimeout(doFilter, 1);
}

function applyExtraNetworkSort(tabname_full) {
    var doSort = function() {
        extraNetworksApplySort[tabname_full](true);
    };
    setTimeout(doSort, 1);
}

var extraNetworksApplyFilter = {};
var extraNetworksApplySort = {};
var activePromptTextarea = {};
let pageSize;
let homePageMatureLevel = "None";

function setupExtraNetworks() {
    setupExtraNetworksForTab('txt2img');
    setupExtraNetworksForTab('img2img');
}

var re_extranet = /<([^:^>]+:[^:]+):[\d.]+>(.*)/;
var re_extranet_g = /<([^:^>]+:[^:]+):[\d.]+>/g;

var re_extranet_neg = /\(([^:^>]+:[\d.]+)\)/;
var re_extranet_g_neg = /\(([^:^>]+:[\d.]+)\)/g;
function tryToRemoveExtraNetworkFromPrompt(textarea, text, isNeg) {
    var m = text.match(isNeg ? re_extranet_neg : re_extranet);
    var replaced = false;
    var newTextareaText;
    var extraTextBeforeNet = opts.extra_networks_add_text_separator;
    if (m) {
        var extraTextAfterNet = m[2];
        var partToSearch = m[1];
        var foundAtPosition = -1;
        newTextareaText = textarea.value.replaceAll(isNeg ? re_extranet_g_neg : re_extranet_g, function(found, net, pos) {
            m = found.match(isNeg ? re_extranet_neg : re_extranet);
            if (m[1] == partToSearch) {
                replaced = true;
                foundAtPosition = pos;
                return "";
            }
            return found;
        });
        if (foundAtPosition >= 0) {
            if (extraTextAfterNet && newTextareaText.substr(foundAtPosition, extraTextAfterNet.length) == extraTextAfterNet) {
                newTextareaText = newTextareaText.substr(0, foundAtPosition) + newTextareaText.substr(foundAtPosition + extraTextAfterNet.length);
            }
            if (newTextareaText.substr(foundAtPosition - extraTextBeforeNet.length, extraTextBeforeNet.length) == extraTextBeforeNet) {
                newTextareaText = newTextareaText.substr(0, foundAtPosition - extraTextBeforeNet.length) + newTextareaText.substr(foundAtPosition);
            }
        }
    } else {
        newTextareaText = textarea.value.replaceAll(new RegExp(`((?:${extraTextBeforeNet})?${text})`, "g"), "");
        replaced = (newTextareaText != textarea.value);
    }

    if (replaced) {
        textarea.value = newTextareaText;
        return true;
    }

    return false;
}

function updatePromptArea(text, textArea, isNeg) {
    if (!tryToRemoveExtraNetworkFromPrompt(textArea, text, isNeg)) {
        textArea.value = textArea.value + opts.extra_networks_add_text_separator + text;
    }

    updateInput(textArea);
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

function extraNetworksTreeProcessFileClick(event, btn, tabname, extra_networks_tabname) {
    /**
     * Processes `onclick` events when user clicks on files in tree.
     *
     * @param event                     The generated event.
     * @param btn                       The clicked `tree-list-item` button.
     * @param tabname                   The name of the active tab in the sd webui. Ex: txt2img, img2img, etc.
     * @param extra_networks_tabname    The id of the active extraNetworks tab. Ex: lora, checkpoints, etc.
     */
    // NOTE: Currently unused.
    return;
}

function extraNetworksTreeProcessDirectoryClick(event, btn, tabname, extra_networks_tabname) {
    /**
     * Processes `onclick` events when user clicks on directories in tree.
     *
     * Here is how the tree reacts to clicks for various states:
     * unselected unopened directory: Diretory is selected and expanded.
     * unselected opened directory: Directory is selected.
     * selected opened directory: Directory is collapsed and deselected.
     * chevron is clicked: Directory is expanded or collapsed. Selected state unchanged.
     *
     * @param event                     The generated event.
     * @param btn                       The clicked `tree-list-item` button.
     * @param tabname                   The name of the active tab in the sd webui. Ex: txt2img, img2img, etc.
     * @param extra_networks_tabname    The id of the active extraNetworks tab. Ex: lora, checkpoints, etc.
     */
    var ul = btn.nextElementSibling;
    // This is the actual target that the user clicked on within the target button.
    // We use this to detect if the chevron was clicked.
    var true_targ = event.target;

    function _expand_or_collapse(_ul, _btn) {
        // Expands <ul> if it is collapsed, collapses otherwise. Updates button attributes.
        if (_ul.hasAttribute("hidden")) {
            _ul.removeAttribute("hidden");
            _btn.dataset.expanded = "";
        } else {
            _ul.setAttribute("hidden", "");
            delete _btn.dataset.expanded;
        }
    }

    function _remove_selected_from_all() {
        // Removes the `selected` attribute from all buttons.
        var sels = document.querySelectorAll("div.tree-list-content");
        [...sels].forEach(el => {
            delete el.dataset.selected;
        });
    }

    function _select_button(_btn) {
        // Removes `data-selected` attribute from all buttons then adds to passed button.
        _remove_selected_from_all();
        _btn.dataset.selected = "";
    }

    function _update_search(_tabname, _extra_networks_tabname, _search_text) {
        // Update search input with select button's path.
        var search_input_elem = gradioApp().querySelector("#" + tabname + "_" + extra_networks_tabname + "_extra_search");
        search_input_elem.value = _search_text;
        updateInput(search_input_elem);
    }


    // If user clicks on the chevron, then we do not select the folder.
    if (true_targ.matches(".tree-list-item-action--leading, .tree-list-item-action-chevron")) {
        _expand_or_collapse(ul, btn);
    } else {
        // User clicked anywhere else on the button.
        if ("selected" in btn.dataset && !(ul.hasAttribute("hidden"))) {
            // If folder is select and open, collapse and deselect button.
            _expand_or_collapse(ul, btn);
            delete btn.dataset.selected;
            _update_search(tabname, extra_networks_tabname, "");
        } else if (!(!("selected" in btn.dataset) && !(ul.hasAttribute("hidden")))) {
            // If folder is open and not selected, then we don't collapse; just select.
            // NOTE: Double inversion sucks but it is the clearest way to show the branching here.
            _expand_or_collapse(ul, btn);
            _select_button(btn, tabname, extra_networks_tabname);
            _update_search(tabname, extra_networks_tabname, btn.dataset.path);
        } else {
            // All other cases, just select the button.
            _select_button(btn, tabname, extra_networks_tabname);
            _update_search(tabname, extra_networks_tabname, btn.dataset.path);
        }
    }
}

function extraNetworksTreeOnClick(event, tabname, extra_networks_tabname) {
    /**
     * Handles `onclick` events for buttons within an `extra-network-tree .tree-list--tree`.
     *
     * Determines whether the clicked button in the tree is for a file entry or a directory
     * then calls the appropriate function.
     *
     * @param event                     The generated event.
     * @param tabname                   The name of the active tab in the sd webui. Ex: txt2img, img2img, etc.
     * @param extra_networks_tabname    The id of the active extraNetworks tab. Ex: lora, checkpoints, etc.
     */
    var btn = event.currentTarget;
    var par = btn.parentElement;
    if (par.dataset.treeEntryType === "file") {
        extraNetworksTreeProcessFileClick(event, btn, tabname, extra_networks_tabname);
    } else {
        extraNetworksTreeProcessDirectoryClick(event, btn, tabname, extra_networks_tabname);
    }
}

function extraNetworksControlSortOnClick(event, tabname, extra_networks_tabname) {
    /**
     * Handles `onclick` events for the Sort Mode button.
     *
     * Modifies the data attributes of the Sort Mode button to cycle between
     * various sorting modes.
     *
     * @param event                     The generated event.
     * @param tabname                   The name of the active tab in the sd webui. Ex: txt2img, img2img, etc.
     * @param extra_networks_tabname    The id of the active extraNetworks tab. Ex: lora, checkpoints, etc.
     */
    var curr_mode = event.currentTarget.dataset.sortmode;
    var el_sort_dir = gradioApp().querySelector("#" + tabname + "_" + extra_networks_tabname + "_extra_sort_dir");
    var sort_dir = el_sort_dir.dataset.sortdir;
    if (curr_mode == "path") {
        event.currentTarget.dataset.sortmode = "name";
        event.currentTarget.dataset.sortkey = "sortName-" + sort_dir + "-640";
        event.currentTarget.setAttribute("title", "Sort by filename");
    } else if (curr_mode == "name") {
        event.currentTarget.dataset.sortmode = "date_created";
        event.currentTarget.dataset.sortkey = "sortDate_created-" + sort_dir + "-640";
        event.currentTarget.setAttribute("title", "Sort by date created");
    } else if (curr_mode == "date_created") {
        event.currentTarget.dataset.sortmode = "date_modified";
        event.currentTarget.dataset.sortkey = "sortDate_modified-" + sort_dir + "-640";
        event.currentTarget.setAttribute("title", "Sort by date modified");
    } else {
        event.currentTarget.dataset.sortmode = "path";
        event.currentTarget.dataset.sortkey = "sortPath-" + sort_dir + "-640";
        event.currentTarget.setAttribute("title", "Sort by path");
    }
    applyExtraNetworkSort(tabname + "_" + extra_networks_tabname);
}

function extraNetworksControlSortDirOnClick(event, tabname, extra_networks_tabname) {
    /**
     * Handles `onclick` events for the Sort Direction button.
     *
     * Modifies the data attributes of the Sort Direction button to cycle between
     * ascending and descending sort directions.
     *
     * @param event                     The generated event.
     * @param tabname                   The name of the active tab in the sd webui. Ex: txt2img, img2img, etc.
     * @param extra_networks_tabname    The id of the active extraNetworks tab. Ex: lora, checkpoints, etc.
     */
    if (event.currentTarget.dataset.sortdir == "Ascending") {
        event.currentTarget.dataset.sortdir = "Descending";
        event.currentTarget.setAttribute("title", "Sort descending");
    } else {
        event.currentTarget.dataset.sortdir = "Ascending";
        event.currentTarget.setAttribute("title", "Sort ascending");
    }
    applyExtraNetworkSort(tabname + "_" + extra_networks_tabname);
}

function extraNetworksControlTreeViewOnClick(event, tabname, extra_networks_tabname) {
    /**
     * Handles `onclick` events for the Tree View button.
     *
     * Toggles the tree view in the extra networks pane.
     *
     * @param event                     The generated event.
     * @param tabname                   The name of the active tab in the sd webui. Ex: txt2img, img2img, etc.
     * @param extra_networks_tabname    The id of the active extraNetworks tab. Ex: lora, checkpoints, etc.
     */
    gradioApp().getElementById(tabname + "_" + extra_networks_tabname + "_tree").classList.toggle("hidden");
    event.currentTarget.classList.toggle("extra-network-control--enabled");
}

function extraNetworksControlRefreshOnClick(event, tabname, extra_networks_tabname) {
    /**
     * Handles `onclick` events for the Refresh Page button.
     *
     * In order to actually call the python functions in `ui_extra_networks.py`
     * to refresh the page, we created an empty gradio button in that file with an
     * event handler that refreshes the page. So what this function here does
     * is it manually raises a `click` event on that button.
     *
     * @param event                     The generated event.
     * @param tabname                   The name of the active tab in the sd webui. Ex: txt2img, img2img, etc.
     * @param extra_networks_tabname    The id of the active extraNetworks tab. Ex: lora, checkpoints, etc.
     */
    var btn_refresh_internal = gradioApp().getElementById(tabname + "_" + extra_networks_tabname + "_extra_refresh_internal");
    btn_refresh_internal.dispatchEvent(new Event("click"));
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

function extraNetworksCopyCardPath(event, path) {
    navigator.clipboard.writeText(path);
    event.stopPropagation();
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
            var card = gradioApp().querySelector(`#${tabname}_${page.replace(" ", "_")}_cards > .card[data-name="${name}"]`);

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
        if (card.id !== `${tabname}_${modelType}_upload_button-card` &&
            card.id !== `${tabname}_${modelType}_add_model-to-workspace` &&
            card.id !== `${tabname}_${modelType}_upload_button-card-private`) {
            const needBlur = judgeLevel(selectedLevel, card.getAttribute('mature-level'));
            const bgFilter = card.querySelector('.set-bg-filter');
            bgFilter.style['filter'] = needBlur ? 'blur(10px)' : 'none';
        }
    })
}

function setupExtraNetworksForTabDiffus(tabname) {
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
    tabs.appendChild(searchDiv);
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
        var cards = gradioApp().querySelectorAll('#' + tabname + '_extra_tabs div.card');

        var reverse = sortOrder.classList.contains("sortReverse");
        var sortKey = sort.querySelector("input").value.toLowerCase().replace("sort", "").replaceAll(" ", "_").replace(/_+$/, "").trim() || "name";
        sortKey = "sort" + sortKey.charAt(0).toUpperCase() + sortKey.slice(1);
        var sortKeyStore = sortKey + "-" + (reverse ? "Descending" : "Ascending") + "-" + cards.length;

        if (sortKeyStore == sort.dataset.sortkey) {
            return;
        }
        sort.dataset.sortkey = sortKeyStore;

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

    // Sort selections
    ["change", "blur", "click"].forEach(function(evt) {
        sort.querySelector("input").addEventListener(evt, applySort);
    });
    sortOrder.addEventListener("click", function() {
        sortOrder.classList.toggle("sortReverse");
        applySort();
    });
    applyFilter();

    extraNetworksApplySort[tabname] = applySort;
    extraNetworksApplyFilter[tabname] = applyFilter;

}

function setupExtraNetworksDiffus() {
    // setupExtraNetworksForTab('txt2img');
    setupExtraNetworksForTabDiffus('img2img');

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


onUiLoaded(function() {
    setPageSize();
    setupExtraNetworksDiffus();
});

window.addEventListener("keydown", function(event) {
    if (event.key == "Escape") {
        closePopup();
    }
});

/**
 * Setup custom loading for this script.
 * We need to wait for all of our HTML to be generated in the extra networks tabs
 * before we can actually run the `setupExtraNetworks` function.
 * The `onUiLoaded` function actually runs before all of our extra network tabs are
 * finished generating. Thus we needed this new method.
 *
 */

// var uiAfterScriptsCallbacks = [];
// var uiAfterScriptsTimeout = null;
// var executedAfterScripts = false;

// function scheduleAfterScriptsCallbacks() {
//     clearTimeout(uiAfterScriptsTimeout);
//     uiAfterScriptsTimeout = setTimeout(function() {
//         executeCallbacks(uiAfterScriptsCallbacks);
//     }, 200);
// }

// onUiLoaded(function() {
//     var mutationObserver = new MutationObserver(function(m) {
//         let existingSearchfields = gradioApp().querySelectorAll("[id$='_extra_search']").length;
//         let neededSearchfields = gradioApp().querySelectorAll("[id$='_extra_tabs'] > .tab-nav > button").length - 2;

//         if (!executedAfterScripts && existingSearchfields >= neededSearchfields) {
//             mutationObserver.disconnect();
//             executedAfterScripts = true;
//             scheduleAfterScriptsCallbacks();
//         }
//     });
//     mutationObserver.observe(gradioApp(), {childList: true, subtree: true});
// });

// uiAfterScriptsCallbacks.push(setupExtraNetworks);
