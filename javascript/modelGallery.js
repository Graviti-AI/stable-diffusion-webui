async function openWorkSpaceDialog(model_type = 'checkpoints') {
    currentModelType = model_type;
    resetParams();
    hasInitTabs.set(model_type, true);
    popup(initDomPage(), 'gallery');
    initalTab(model_type);
    getPrivateModelList({model_type: model_type, page: 1, loading: false, model_workspace: 'private'});
    getPersonalModelList({model_type: model_type, page: 1, loading: true, model_workspace: 'personal'});
    getPublicModelList({init:true, model_type: model_type, page: 1, loading: true, model_workspace: 'public'});
}

function resetParams() {
    searchValue = '';
    hasInitTabs.clear();
    tabSearchValueMap.clear();
    gallertModelScrollloads = [];
    document.removeEventListener('tabby', tabEventListener);
    gallerySearchBtn && gallerySearchBtn.removeEventListener('input', debounceSearchModelGallery);
    gallertModelCurrentPage = {
        'checkpoints': 1,
        'lora': 1,
        'hypernetworks': 1,
        'textual_inversion': 1,
        'lycoris': 1
    };

    galleryModelTotalPage = {
        personal: {
            'checkpoints': 1,
            'lora': 1,
            'hypernetworks': 1,
            'textual_inversion': 1,
            'lycoris': 1
        },
        public: {
            'checkpoints': 1,
            'lora': 1,
            'hypernetworks': 1,
            'textual_inversion': 1,
            'lycoris': 1
        },
        private: {
            'checkpoints': 1,
            'lora': 1,
            'hypernetworks': 1,
            'textual_inversion': 1,
            'lycoris': 1
        }
    }
}

function getPrivateModelList({ model_type, page, loading, model_workspace, switchPage }) {
    const requestUrl = connectNewModelApi ? `/internal/private_models?model_type=${model_type_mapper[model_type]}&search_value=${searchValue}&page=${page}&page_size=${pageSize}` 
        : `/sd_extra_networks/models?page_name=${model_type}&page=${page}&search_value=${searchValue}&page_size=${pageSize}&need_refresh=false`;
    const promise = fetchGet(requestUrl);
    getModelGalleryPageDataAndUpdateList({ model_type, page, loading, model_workspace, promise, switchPage});
}

async function  getPublicModelList({ init, model_type, page, loading, model_workspace, switchPage, sl, refreshTabLock }) {
    const requestUrl = connectNewModelApi ? `/internal/models?model_type=${model_type_mapper[model_type]}&search_value=${searchValue}&page=${page}&page_size=${pageSize}` 
        : `/sd_extra_networks/models?page_name=${model_type}&page=${page}&search_value=${searchValue}&page_size=${pageSize}&need_refresh=false`;
    const promise = fetchGet(requestUrl);
    getModelGalleryPageDataAndUpdateList({ init, model_type, page, loading, model_workspace, promise, switchPage, sl, refreshTabLock});
}

function getPersonalModelList({ model_type, page, loading, model_workspace }) {
    const promise = fetchGet(`/internal/favorite_models?model_type=${model_type_mapper[model_type]}&page=${page}&page_size=100000`);
    getModelGalleryPageDataAndUpdateList({ model_type, page, loading, model_workspace, promise});
}

function judgeLevel(globalLevel, pictureLevel) {
    if (globalLevel === 'None') {
        return pictureLevel === 'Soft' || pictureLevel === 'Mature';
    } else if (globalLevel === 'Soft') {
        return pictureLevel === 'Mature'
    }
    return false;
}


async function handleModelData({init, response, model_type, model_workspace, switchPage, sl, refreshTabLock}) {
    const cardsParentNode = model_workspace === 'personal' ? gradioApp().querySelector(`#${model_workspace}-${model_type}`)
         : gradioApp().querySelector(`#${model_workspace}-${model_type}-cards`);
    const { model_list, total_count: totalCount } = await response.json();
    // set total page
    galleryModelTotalPage[model_workspace][model_type] = Math.ceil(totalCount / pageSize);
    // remove child node
    if(!switchPage) {
        const cards = cardsParentNode.querySelectorAll(".card");
        cards.forEach(card => {
            cardsParentNode.removeChild(card);
        })
        if (model_list && model_list.length  === 0) {
            const cardNode = document.createElement('li');
            cardsParentNode.appendChild(cardNode);
            cardNode.outerHTML = `
            <li class="card"
                id="${model_workspace}_${model_type}_upload_button-card" 
                style="display: block; white-space: nowrap; text-align: center; background-image: none; background-color: rgba(171, 176, 177, 0.4);" 
                onclick="uploadModel()" 
                model_type="${model_type}" 
                uppy_dashboard_title="${model_type} files only. ( < 5 MB)" 
                max_model_size_mb="5">
                <span class="helper" style="display: inline-block; height: 100%; vertical-align: middle;"></span>
                <img id="${model_workspace}_${model_type}-plus-sign" style="max-width: 100%;margin: auto; vertical-align: middle; display:inline-block" src="/components/icons/plus.png">
                <img id="${model_workspace}_${model_type}-loading-sign" style="margin: auto; vertical-align: middle; display: none" src="/components/icons/loading.gif">
                <div class="actions" style="color:white;">Upload ${model_type.replace('_', ' ').replace(model_type[0],model_type[0].toUpperCase())} Models</div>
            </li>
            `
            
        }
    }
    const operateButtonName = model_workspace === 'personal' ? "Remove from workspace" : "Add to workspace";
    const matureLevel = gradioApp().querySelector('#model-gallery-meture-level');
    
    // add new child
    model_list.forEach(item => {
        const cardNode = document.createElement('li');
        cardNode.className = 'card';
        
        cardNode.setAttribute('filename', item.name);
        

        cardNode.setAttribute('mature-level', item.preview_mature_level || 'None');

        cardNode.innerHTML = `
            <div class="set-bg-filter"></div>
            <div class="metadata-button" title="Show metadata" onclick="extraNetworksRequestMetadata(event, '${model_type}', '${item.name}')"></div>
            <div class="operation-button" onclick="handleModelAddOrRemoved('${item.id}', '${model_type}', '${model_workspace}')">${operateButtonName}</div>
            <div class="actions">
                <span class="name">${item.name_for_extra}</span>
                <span class="description"></span>
            </div>

        `
        const bgFilter = cardNode.querySelector('.set-bg-filter');
        if (item.preview) {
            const preview = item.preview.replace(/\s/g, encodeURIComponent(' '));
            bgFilter.style.backgroundImage = `url('${preview}')`;
        }

        if (judgeLevel(matureLevel.value, cardNode.getAttribute('mature-level'))) {
            bgFilter.style['filter'] = 'blur(10px)';
        }

        cardsParentNode.appendChild(cardNode);
    })
    init && initLoadMore(model_type);
    refreshTabLock && updateLockStatus(model_type);
    sl && sl.unLock()
}

function updateLockStatus(modelType) {
    gallertModelScrollloads.forEach((scrollload, index) => {
        index === defaultModelType.findIndex(item => item === modelType) ? scrollload.unLock() : scrollload.lock()
    })
}

async function getModelGalleryPageDataAndUpdateList({ init, model_type, loading=true, model_workspace, promise, switchPage, sl, refreshTabLock}) {
    // loading
    if (loading) {
        notifier.asyncBlock(promise, (response) => {
            handleModelData({response, model_type, model_workspace, switchPage, refreshTabLock, init })
        });
    } else {
        const response = await promise;
        handleModelData({  response, model_type, model_workspace, switchPage, sl })
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
                    <span>Mature Content</span>
                    <select onchange="changeMatureLevel(this)" id="model-gallery-meture-level">
                        <option value="None">None</option>
                        <option value="Soft">Soft</option>
                        <option value="Mature">Mature</option>
                    </select>
                </div>
            </div>
            <div class="personal-workspace-model-list">
                <ul personal-data-tabs>
                    <li><a checkpoints href="#personal-checkpoints">Checkpoints</a></li>
                    <li><a textual_inversion  href="#personal-textual_inversion">Textual Inversion</a></li>
                    <li><a hypernetworks href="#personal-hypernetworks">Hypernetworks</a></li>
                    <li><a lora href="#personal-lora">Lora</a></li>
                    <li><a lycoris href="#personal-lycoris">LyCORIS/LoCon</a></li>
                </ul>
                <div class="gallery-cards">
                    <ul id="personal-checkpoints" class="extra-network-cards" id="personal-checkpoints-cards"></li></ul>
                    <ul id="personal-textual_inversion" class="extra-network-cards" id="personal-textual_inversion-cards"></li></ul>
                    <ul id="personal-hypernetworks" class="extra-network-cards" id="personal-hypernetworks-cards"></li></ul>
                    <ul id="personal-lora" class="extra-network-cards" id="personal-lora-cards"></li></ul>
                    <ul id="personal-lycoris" class="extra-network-cards" id="personal-lycoris-cards"></li></ul>
                </div>
            </div>
        </div>
        <div class="public-workspace">
            <div class="public-workspace-top">
                <input id="gallery-search" class="scroll-hide search" placeholder="Search with model names, hashes, tags, trigger words"></input>
                <div class="search-btn"><button class="upload-btn" onclick="uploadModel()">Upload Models</button></div>
            </div>
            <div class="public-workspace-title">
                <span>Model Gallery</span>
            </div>
            <div class="public-workspace-model-list">
                <ul public-data-tabs>
                    <li><a checkpoints href="#public-checkpoints">Checkpoints</a></li>
                    <li><a textual_inversion  href="#public-textual_inversion">Textual Inversion</a></li>
                    <li><a hypernetworks href="#public-hypernetworks">Hypernetworks</a></li>
                    <li><a lora href="#public-lora">Lora</a></li>
                    <li><a lycoris href="#public-lycoris">LyCORIS/LoCon</a></li>
                </ul>
                <div class="gallery-cards">
                    <p>Private Models</p>
                    <div id="private-checkpoints" >
                        <ul id="private-checkpoints-cards" class="extra-network-cards scrollload-content">
                        </ul>
                    </div>
                    <div id="private-textual_inversion" hidden="hidden">
                        <ul id="private-textual_inversion-cards" class="extra-network-cards scrollload-content">
                        </ul>
                    </div>
                    <div id="private-hypernetworks" hidden="hidden">
                        <ul id="private-hypernetworks-cards" class="extra-network-cards scrollload-content">
                        </ul>
                    </div>
                    <div id="private-lora" hidden="hidden">
                        <ul id="private-lora-cards" class="extra-network-cards scrollload-content">
                        </ul>
                    </div>
                    <div id="private-lycoris" hidden="hidden">
                        <ul id="private-lycoris-cards" class="extra-network-cards scrollload-content">
                        </ul>
                    </div>
                    <p>Public Models</p>
                    <div id="public-checkpoints" >
                        <div class="scrollload-container" model-type="checkpoints" workspace="public">
                            <ul id="public-checkpoints-cards" class="extra-network-cards scrollload-content">
                            </ul>
                        </div>
                    </div>
                    <div id="public-textual_inversion">
                        <div class="scrollload-container" model-type="textual_inversion" workspace="public">
                            <ul id="public-textual_inversion-cards" class="extra-network-cards scrollload-content">
                            </ul>
                        </div>
                    </div>
                    <div id="public-hypernetworks">
                        <div class="scrollload-container" model-type="hypernetworks" workspace="public">
                            <ul id="public-hypernetworks-cards" class="extra-network-cards scrollload-content">
                               
                            </ul>
                        </div>
                    </div>
                    <div id="public-lora">
                        <div class="scrollload-container" model-type="lora" workspace="public">
                            <ul id="public-lora-cards" class="extra-network-cards scrollload-content">
                               
                            </ul>
                        </div>
                    </div>
                    <div id="public-lycoris">
                        <div class="scrollload-container" model-type="lycoris" workspace="public">
                            <ul id="public-lycoris-cards" class="extra-network-cards scrollload-content">
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
    let msgType = 'Add';
    if (model_workspace === 'personal') {
        promise = fetchDelete(`/internal/favorite_models/${model_id}`);
        msgType = 'Remove'
    } else {
        promise = fetchPost({ data: {model_id: model_id}, url: `/internal/favorite_models` });
    }
    notifier.asyncBlock(promise, async (response) => {
        if (response.status === 200) {
            notifier.success(`${msgType} Success`)
            getPersonalModelList({model_type: model_type, page: 1, loading: true, model_workspace: 'personal'});
            fetchHomePageDataAndUpdateList({tabname: currentModelTab, model_type, page: 1, loading:false})
            if (model_type === 'checkpoints') {
                const refeshCheckpointBtn = gradioApp().querySelector('#refresh_sd_model_checkpoint_dropdown');
                refeshCheckpointBtn.click();
            }
        } else if (response.status === 409) {
            const { detail } = await response.json();
            notifier.alert(detail);
        } else {
            notifier.alert(`${msgType} Failed`)
        }
    });
}

function setMatureLevel({modelList, globalLevel}) {
    modelList.forEach(card => {
        if (card.id !== `personal_${currentModelType}_upload_button-card` && card.id !== `public${currentModelType}_upload_button-card`) {
            const needBlur = judgeLevel(globalLevel, card.getAttribute('mature-level'));
            const bgFilter = card.querySelector('.set-bg-filter');
            bgFilter.style['filter'] = needBlur ? 'blur(10px)' : 'none';
        }
    })
}

function changeMatureLevel(self) {
    const personalCardList = gradioApp().querySelector(`#personal-${currentModelType}`).querySelectorAll('.card');
    setMatureLevel({modelList: personalCardList, globalLevel: self.value});
    const privateCardList = gradioApp().querySelector(`#private-${currentModelType}`).querySelectorAll('.card');
    setMatureLevel({ modelList: privateCardList, globalLevel: self.value});
    const publicCardList = gradioApp().querySelector(`#public-${currentModelType}`).querySelectorAll('.card');
    setMatureLevel({modelList: publicCardList, globalLevel: self.value});
}

function uploadModel() {
    gradioApp().querySelector(`#${currentModelTab}_${currentModelType}_upload_button-card`).click();
}

function removeAllTabScrollBottomDom() {
    defaultModelType.forEach(modelType => {
        const scrollBottomDom = gradioApp().querySelector(`#public-${modelType}`).querySelector('.scrollload-bottom');
        scrollBottomDom.remove();
    })
}

function searchPublicModels(event) {
    searchValue = event.target.value.toLowerCase();
    gallertModelCurrentPage[currentModelType] = 1;
    tabSearchValueMap.set(currentModelType, searchValue);
    getPrivateModelList({model_type: currentModelType, page: 1, loading: true, model_workspace: 'private'});
    gallertModelScrollloads = [];
    // must remove load more dom to reinitialize
    removeAllTabScrollBottomDom();
    getPublicModelList({model_type: currentModelType, page: 1, loading: true, model_workspace: 'public', init: true});
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

function togglePrivateModelTab(modelType) {
    defaultModelType.forEach(typeItem => {
        const modelCard = gradioApp().querySelector(`#private_${modelType}`)
        if (typeItem === modelType) {
            modelCard.removeAttribute('hidden');
        } else {
            modelCard.setAttribute('hidden', 'hidden');
        }
    })
}

function tabEventListener (event) {
    const content = event.detail.content;
    const [type, modelType] = content.id.split('-');
    currentModelType = modelType;
    const mapValue = tabSearchValueMap.get(modelType) === undefined ? '' : tabSearchValueMap.get(modelType);
    console.log(modelType, 1111);
    if (type === 'public') {
        // not refresh data while at other page
        
        if (!hasInitTabs.get(modelType) || ( mapValue !== searchValue)) {
            getPublicModelList({model_type: currentModelType, page: 1, model_workspace: type, refreshTabLock: true})
            getPrivateModelList({model_type: currentModelType, page: 1, model_workspace: 'private' })
        } else {
            updateLockStatus(modelType);
        }
        personalTabs.toggle(`#personal-${modelType}`);
    } else {
        // not refresh data while on other page
        if (!hasInitTabs.get(modelType) || (mapValue !== searchValue)) {
            getPersonalModelList({model_type: currentModelType, page: 1, model_workspace: type})
        }
        publicTabs.toggle(`#public-${modelType}`);
    }
    togglePrivateModelTab(modelType);
    tabSearchValueMap.set(modelType, searchValue);
    hasInitTabs.set(modelType, true);
}

const debounceSearchModelGallery = debounceSearchModels(searchPublicModels);

function initalTab (model_type) {
    personalTabs = new Tabby('[personal-data-tabs]', {
        default: `[${model_type}]` // The selector to use for the default tab
    });

    publicTabs = new Tabby('[public-data-tabs]', {
        default: `[${model_type}]` // The selector to use for the default tab
    });

    document.addEventListener('tabby', tabEventListener, false);

    gallerySearchBtn = gradioApp().querySelector('#gallery-search');

    gallerySearchBtn.addEventListener("input", debounceSearchModelGallery);
}

function refreshModelsGallery() {
    getPrivateModelList({model_type: 'checkpoints', page: 1, loading: true, model_workspace: 'private'});
    getPublicModelList({model_type: 'checkpoints', page: 1, loading: true, model_workspace: 'public'});
    getPersonalModelList({model_type: 'checkpoints', page: 1, loading: true, model_workspace: 'personal'});
}

function initLoadMore(model_type) {
    const scrollerContainerList = gradioApp().querySelectorAll('.scrollload-container');
    Array.prototype.slice.call(scrollerContainerList).forEach((container, index) => {
        gallertModelScrollloads.push(
            new Scrollload({
                container: container,
                loadMore: function(sl) {
                    const modelType = container.getAttribute('model-type');
                    if (currentModelType !== modelType) return;
                    if (gallertModelCurrentPage[modelType] >= galleryModelTotalPage.public[modelType]) {
                      // call noMoreData when on the last page
                      sl.noMoreData()
                      return
                    }
                    // add page
                    gallertModelCurrentPage[modelType] += 1;
                    getPublicModelList({model_type: modelType, page:  gallertModelCurrentPage[modelType], loading: false, model_workspace: 'public', switchPage: true, sl});
                    getPrivateModelList({model_type: modelType, page:  gallertModelCurrentPage[modelType], loading: false, model_workspace: 'private', switchPage: true})
                },
                isInitLock: index === defaultModelType.findIndex(item => item === model_type) ? false : true,
                enablePullRefresh: false,
                window: gradioApp().querySelector('.global-popup'),
                noMoreDataHtml: `
                <a onclick="uploadModel()" class="no-more-btn lg primary gradio-button">The end of list, click to add more</a>
                `,
                // threshold: 20,
            })
        )
    })
}
