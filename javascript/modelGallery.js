function openWorkSpaceDialog() {
    popup(initDomPage(), 'gallery');
    initalTab();
    initLoadMore();
    getPrivateModelList({tabname: currentModelTab, model_type: 'checkpoints', page: 1, loading: false, model_workspace: 'private'});
    getPersonalModelList({tabname: currentModelTab, model_type: 'checkpoints', page: 1, loading: false, model_workspace: 'personal'});
    getPublicModelList({tabname: currentModelTab, model_type: 'checkpoints', page: 1, loading: false, model_workspace: 'public'});
}

function getPrivateModelList({ model_type, page, tabname, loading, model_workspace, switchPage }) {
    const searchValue = gradioApp().querySelector('#gallery-search').value.toLowerCase();
    const promise = fetchGet(`/internal/private/${model_type_mapper[model_type]}?search_value=${searchValue}&page=${page}&page_size=${pageSize}`);
    getPageDataAndUpdateList({tabname, model_type, page, loading, model_workspace, promise, switchPage});
}

function getPublicModelList({ model_type, page, tabname, loading, model_workspace, switchPage }) {
    const searchValue = gradioApp().querySelector('#gallery-search').value.toLowerCase();
    const promise = fetchGet(`/internal/models/${model_type_mapper[model_type]}?search_value=${searchValue}&page=${page}&page_size=${pageSize}`);
    getPageDataAndUpdateList({tabname, model_type, page, loading, model_workspace, promise, switchPage});
}

function getPersonalModelList({ model_type, page, tabname, loading, model_workspace }) {
    const promise = fetchGet(`/internal/favorite/${model_type_mapper[model_type]}?page=${page}&page_size=100000`);
    getPageDataAndUpdateList({tabname, model_type, page, loading, model_workspace, promise});
}

function judgeLevel(globalLevel, pictureLevel) {
    if (globalLevel === 'None') {
        return pictureLevel === 'Soft' || pictureLevel === 'Mature';
    } else if (globalLevel === 'Soft') {
        return pictureLevel === 'Mature'
    }
    return false;
}


async function handleModelData({tabname, response, model_type, model_workspace, switchPage}) {
    const cardsParentNode = model_workspace === 'personal' ? gradioApp().querySelector(`#${model_workspace}-${model_type}`)
         : gradioApp().querySelector(`#${model_workspace}-${model_type}-cards`);
    const { model_list, page: resPage, total_count: totalCount, allow_negative_prompt } = await response.json();
    // set total page
    galleryModelTotalPage[model_workspace][model_type] = Math.ceil(totalCount / pageSize);
    // remove child node
    if(!switchPage) {
        const cards = cardsParentNode.querySelectorAll(".card");
        cards.forEach(card => {
            cardsParentNode.removeChild(card);
        })
        if (model_list.length  === 0) {
            const cardNode = document.createElement('li');
            cardNode.className = 'card card-no-model';
            cardsParentNode.appendChild(cardNode);
        }
    }
    const operateButtonName = model_workspace === 'personal' ? "Remove from workspace" : "Add to workspace";
    const matureLevel = gradioApp().querySelector('#model-gallery-meture-level');
    
    // add new child
    model_list.forEach(item => {
        const cardNode = document.createElement('li');
        cardNode.className = 'card';
        
        cardNode.setAttribute('filename', item.name);
        if (item.preview) {
            cardNode.style.backgroundImage = `url(${item.preview})`;
        }

        if (judgeLevel(matureLevel.value, item.mature_level )) {
            cardNode.setAttribute('style', 'filter:blur(10px)');
        }

        cardNode.setAttribute('mature-level', item.mature_level);

        cardNode.innerHTML = `
            <div class="metadata-button" title="Show metadata" onclick="extraNetworksRequestMetadata(event, '${model_type}', '${item.name}')"></div>
            <div class="operation-button" onclick="handleModelAddOrRemoved('${item.id}', '${model_type}', '${model_workspace}')">${operateButtonName}</div>
            <div class="actions">
                <span class="name">${item.name}</span>
                <span class="description"></span>
            </div>

        `
        cardsParentNode.appendChild(cardNode);
    })

}

async function getPageDataAndUpdateList({tabname, model_type, loading=true, model_workspace, promise, switchPage}) {
    // loading
    if (loading) {
        notifier.asyncBlock(promise, (response) => {
            handleModelData({response, tabname, model_type, model_workspace, switchPage })
        });
    } else {
        const response = await promise;
        handleModelData({  response, tabname, model_type, model_workspace, switchPage })
    }
}

function initDomPage() {
    const fragment = new DocumentFragment();

    const galleryContainerNode = document.createElement('div');
    galleryContainerNode.className = 'gallery-container';

    galleryContainerNode.innerHTML = `
        <div class="personal-workspace">
            <div class="personal-workspace-top">
                <span>Personal Workspace</span>
                <div class="personal-workspace-top-mature">
                    <span>Mature Level</span>
                    <select onchange="changeMatureLevel(this)" id="model-gallery-meture-level">
                        <option value="None">None</option>
                        <option value="Soft">Soft</option>
                        <option value="Mature">Mature</option>
                    </select>
                </div>
            </div>
            <div class="personal-workspace-model-list">
                <ul personal-data-tabs>
                    <li><a data-tabby-default href="#personal-checkpoints">Checkpoints</a></li>
                    <li><a href="#personal-textual_inversion">Textual Inversion</a></li>
                    <li><a href="#personal-hypernetworks">Hypernetworks</a></li>
                    <li><a href="#personal-lora">Lora</a></li>
                </ul>
                <div class="gallery-cards">
                    <ul id="personal-checkpoints" class="extra-network-cards" id="personal-checkpoints-cards"><li class="card"></li></ul>
                    <ul id="personal-textual_inversion" class="extra-network-cards" id="personal-textual_inversion-cards"><li class="card"></li></ul>
                    <ul id="personal-hypernetworks" class="extra-network-cards" id="personal-hypernetworks-cards"><li class="card"></li></ul>
                    <ul id="personal-lora" class="extra-network-cards" id="personal-lora-cards"><li class="card"></li></ul>
                </div>
            </div>
        </div>
        <div class="public-workspace">
            <div class="public-workspace-top">
                <input id="gallery-search" class="scroll-hide search" placeholder="Search with model names, hashes, tags, trigger words"></input>
                <div class="search-btn"><button class="upload-btn" onclick="uploadModel()">Upload Models</button></div>
            </div>
            <div class="public-workspace-model-list">
                <ul public-data-tabs>
                    <li><a data-tabby-default href="#public-checkpoints">Checkpoints</a></li>
                    <li><a href="#public-textual_inversion">Textual Inversion</a></li>
                    <li><a href="#public-hypernetworks">Hypernetworks</a></li>
                    <li><a href="#public-lora">Lora</a></li>
                </ul>
                <div class="gallery-cards">
                    <div id="public-checkpoints" >
                        <p>Private Models</p>
                        <div id="private-checkpoints-cards" class="extra-network-cards">
                            <div class="card"></div>
                        </div>
                        <p>Public Models</p>
                        <div class="scrollload-container" model-type="checkpoints" workspace="public">
                            <ul id="public-checkpoints-cards" class="extra-network-cards scrollload-content">
                                <li class="card"></li>
                            </ul>
                        </div>
                    </div>
                    <div id="public-textual_inversion">
                        <p>Private Models</p>
                        <div id="private-textual_inversion-cards" class="extra-network-cards">
                            <div class="card"></div>
                        </div>
                        <p>Public Models</p>
                        <div class="scrollload-container" model-type="textual_inversion" workspace="public">
                            <ul id="public-textual_inversion-cards" class="extra-network-cards scrollload-content">
                                <li class="card"></li>
                            </ul>
                        </div>
                    </div>
                    <div id="public-hypernetworks">
                        <p>Private Models</p>
                        <ul id="private-hypernetworks-cards" class="extra-network-cards">
                            <div class="card"></div>
                        </ul>
                        <p>Public Models</p>
                        <div class="scrollload-container" model-type="hypernetworks" workspace="public">
                            <ul id="public-hypernetworks-cards" class="extra-network-cards scrollload-content">
                                <li class="card"></li>
                            </ul>
                        </div>
                    </div>
                    <div id="public-lora">
                        <p>Private Models</p>
                        <ul id="private-lora-cards" class="extra-network-cards">
                            <li class="card"></li>
                        </ul>
                        <p>Public Models</p>
                        <div class="scrollload-container" model-type="lora" workspace="public">
                            <ul id="public-lora-cards" class="extra-network-cards scrollload-content">
                                <li class="card"></li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `
    fragment.appendChild(galleryContainerNode);

    return fragment;
}

async function handleModelAddOrRemoved(model_id, model_type, model_workspace) {
    let promise = null;
    if (model_workspace === 'personal') {
        promise = fetchDelete(`/internal/favorite/${model_id}`);
    } else {
        promise = fetchPost({ data: {model_id: model_id}, url: `/internal/favorite` });
    }
    notifier.asyncBlock(promise, async (response) => {
        if (response.status === 200 && response.statusText === 'OK') {
            getPersonalModelList({tabname: currentModelTab, model_type: model_type, page: 1, loading: true, model_workspace: 'personal'});
        }
    });
}

function setMatureLevel({list, globalLevel}) {
    list.forEach(card => {
        const needBlur = judgeLevel(globalLevel, card.getAttribute('mature-level'));
        card.setAttribute('style', needBlur ? 'filter:blur(10px)' : 'filter:none');
    })
}

function changeMatureLevel(self) {
    const personalCardList = gradioApp().querySelector(`#personal-${currentModelTab.personal}`).querySelectorAll('.card');
    setMatureLevel({personalCardList, globalLevel: self.value});
    const privateCardList = gradioApp().querySelector(`#private-${currentModelTab.public}`).querySelectorAll('.card');
    setMatureLevel({privateCardList, globalLevel: self.value});
    const publicCardList = gradioApp().querySelector(`#public-${currentModelTab.public}`).querySelectorAll('.card');
    setMatureLevel({publicCardList, globalLevel: self.value});
}

function uploadModel() {
    gradioApp().querySelector(`#${currentModelTab}_${currentModelType.public}_upload_button-card`).click();
}

function searchPublicModels() {
    getPrivateModelList({tabname: currentModelTab, model_type: 'checkpoints', page: 1, loading: true, model_workspace: 'private'});
    getPublicModelList({tabname: currentModelTab, model_type: 'checkpoints', page: 1, loading: true, model_workspace: 'public'});
}

function debounceSearchModels(func, wait=1000, immediate) {
    let timer = null;
    return function () {
        let context = this;
        let args = arguments;
        if (timer) clearTimeout(timer);
        if (immediate) {
            const callNow = !timer;
            timer = setTimeout(() => {
                timer = null;
            }, wait)
            if (callNow) func.apply(context, args)
        } else {
            timer = setTimeout(function(){
                func.apply(context, args)
            }, wait);
        }
    }
}

const debounceSearchModelGallery = debounceSearchModels(searchPublicModels);

function initalTab () {
    currentModelTab = gradioApp().querySelector("#tabs > div.tab-nav > button.selected").textContent.trim();
    new Tabby('[personal-data-tabs]', {
        default: '[data-tabby-default]' // The selector to use for the default tab
    });

    new Tabby('[public-data-tabs]', {
        default: '[data-tabby-default]' // The selector to use for the default tab
    });

    document.addEventListener('tabby', function (event) {
        const content = event.detail.content;
        const [type, modelType] = content.id.split('-');
        currentModelType[type] = modelType;

        if (type === 'public') {
            gallertModelScrollloads.forEach((scrollload, index) => {
                index === defaultModelType.findIndex(item => item === modelType) ? scrollload.unLock() : scrollload.lock()
            })
            console.log(gallertModelScrollloads, 'gallertModelScrollloads')
            // not refresh data while at other page
            if (gallertModelCurrentPage[modelType] === 1) {
                getPublicModelList({tabname: currentModelTab, model_type: currentModelType[type], page: 1, model_workspace: type})
                getPrivateModelList({tabname: currentModelTab, model_type: currentModelType[type], page: 1, model_workspace: 'private' })
            }
        } else {
            // not refresh data while on other page
            if (gallertModelCurrentPage[modelType] === 1) {
                getPersonalModelList({tabname: currentModelTab, model_type: currentModelType[type], page: 1, model_workspace: type})
            }
        }
        
        
    }, false);

    const gallerySearchBtn = gradioApp().querySelector('#gallery-search');

    gallerySearchBtn.addEventListener("input", debounceSearchModelGallery);
}

function refreshModelsGallery(tabname) {
    getPrivateModelList({tabname, model_type: 'checkpoints', page: 1, loading: true, model_workspace: 'private'});
    getPublicModelList({tabname, model_type: 'checkpoints', page: 1, loading: true, model_workspace: 'public'});
    getPersonalModelList({tabname, model_type: 'checkpoints', page: 1, loading: true, model_workspace: 'personal'});
}

function initLoadMore() {
    const scrollerContainerList = gradioApp().querySelectorAll('.scrollload-container');
    Array.prototype.slice.call(scrollerContainerList).forEach((container, index) => {
        gallertModelScrollloads.push(
            new Scrollload({
                container: container,
                loadMore: function(sl) {
                    const modelType = container.getAttribute('model-type');
                    console.log(gallertModelCurrentPage,container, galleryModelTotalPage.public[modelType], 111)
                    if (gallertModelCurrentPage[modelType] === galleryModelTotalPage.public[modelType]) {
                      // call noMoreData when on the last page
                      sl.noMoreData()
                      return
                    }
                    // add page
                    gallertModelCurrentPage[modelType] += 1;
                    Promise.all([getPrivateModelList({tabname: currentModelTab, model_type: modelType, page:  gallertModelCurrentPage[modelType], loading: false, model_workspace: 'private', switchPage: true}),getPublicModelList({tabname: currentModelTab, model_type: modelType, page:  gallertModelCurrentPage[modelType], loading: false, model_workspace: 'public', switchPage: true})])
                    sl.unLock()
                },
                isInitLock: index === 0 ? false : true,
                enablePullRefresh: false,
                // threshold: 20,
            })
        )
    })
}