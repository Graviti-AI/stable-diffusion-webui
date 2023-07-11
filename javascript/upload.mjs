import { setup_uppy_for_upload_button } from "/public/js/upply.mjs"

if (typeof setup_uppy_for_upload_button != "undefined") {
    const tus_endpoint = '/files/';
    const model_verification_endpoint= '/verify-model-existence';
    const uppy_object_map = new Map();

    function refresh_model_list_when_upload_complete_wrapper(tabname) {
        function refresh_model_list_when_upload_complete(complete_array) {
            var model_refresh_button = gradioApp().querySelector(`#${tabname}_extra_refresh`);
            model_refresh_button.click();
        }
        return refresh_model_list_when_upload_complete;
    }

    function clickCorrectTabForModelType(fileName, sha256, model_type, real_model_type) {
        if (model_type != real_model_type) {
            notifier.warning(`${fileName} is a ${real_model_type} but not ${model_type}`);
            const tab = gradioApp().querySelector(`#tabby-toggle_personal-${real_model_type}`);
            tab.click();
        }
    }

    function add_model_to_favorite_if_exists_wrapper(tabname, model_type) {
        function add_model_to_favorite_if_exists(fileName, sha256, req_model_type, res_model_type) {
            const real_model_type = Object.keys(model_type_mapper).find(key => model_type_mapper[key] === res_model_type);

            clickCorrectTabForModelType(fileName, sha256, req_model_type, real_model_type);
            getPersonalModelList({model_type: real_model_type, page: 1, loading: true, model_workspace: 'personal'});
            fetchHomePageDataAndUpdateList({tabname: tabname, model_type: real_model_type, page: 1, loading: false});
            if (real_model_type === 'checkpoints') {
                const refeshCheckpointBtn = gradioApp().querySelector('#refresh_sd_model_checkpoint_dropdown');
                refeshCheckpointBtn.click();
            }
        }
        return add_model_to_favorite_if_exists;
    }

    function model_type_check_callback_wrapper(tabname, model_type) {
        function model_type_check_callback(fileName, sha256, req_model_type, res_model_type) {
            const real_model_type = Object.keys(model_type_mapper).find(key => model_type_mapper[key] === res_model_type);

            clickCorrectTabForModelType(fileName, sha256, req_model_type, real_model_type);
            getPersonalModelList({model_type: real_model_type, page: 1, loading: true, model_workspace: 'personal'});
            fetchHomePageDataAndUpdateList({tabname: tabname, model_type: real_model_type, page: 1, loading: false});
            if(gallertModelCurrentPage[real_model_type] === 1) {
                getPublicModelList({model_type: real_model_type, page: 1, loading: true, model_workspace: 'public'});
            }
            if (real_model_type === 'checkpoints') {
                const refeshCheckpointBtn = gradioApp().querySelector('#refresh_sd_model_checkpoint_dropdown');
                refeshCheckpointBtn.click();
            }
        }
        return model_type_check_callback;
    }

    function register_button(elem_node){
        const tabname = elem_node.getAttribute("tabname");
        const model_type = elem_node.getAttribute("model_type");

        if (uppy_object_map.has(elem_node.id))
        {
            var uppy = uppy_object_map.get(elem_node.id);
            uppy.close();
            uppy = null;
            uppy_object_map.delete(elem_node.id);

            uppy = setup_uppy_for_upload_button(
                elem_node,
                tus_endpoint,
                model_verification_endpoint,
                refresh_model_list_when_upload_complete_wrapper(tabname),
                null,
                add_model_to_favorite_if_exists_wrapper(tabname, model_type),
                model_type_check_callback_wrapper(tabname, model_type)
            );
            uppy_object_map.set(elem_node.id, uppy);

        } else {
            const uppy = setup_uppy_for_upload_button(
                elem_node,
                tus_endpoint,
                model_verification_endpoint,
                refresh_model_list_when_upload_complete_wrapper(tabname),
                null,
                add_model_to_favorite_if_exists_wrapper(tabname, model_type),
                model_type_check_callback_wrapper(tabname, model_type)
            );

            uppy_object_map.set(elem_node.id, uppy);
        }

    }

    window.register_button = register_button;

    onUiLoaded(() => {
        var buttons = gradioApp().querySelectorAll('.model-upload-button');
        buttons.forEach(register_button);
        var observeUploadButtonChange = new MutationObserver((mutationList, observer) => {
            mutationList.forEach((item) => {
                item.addedNodes.forEach((node) => {
                    if (node.nodeName.toLowerCase() == "div" && node.classList.contains("model-upload-button")) {
                        register_button(button);
                    }
                });
            });
        });
        observeUploadButtonChange.observe( gradioApp().querySelector('#txt2img_extra_tabs'), { childList:true, subtree:true });
        observeUploadButtonChange.observe( gradioApp().querySelector('#img2img_extra_tabs'), { childList:true, subtree:true });
    });
}
