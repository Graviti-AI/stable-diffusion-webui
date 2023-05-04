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

    function register_button(elem_node){
        if (uppy_object_map.has(elem_node.id))
        {
            var uppy = uppy_object_map.get(elem_node.id);
            uppy.close();
            uppy = null;
            uppy_object_map.delete(elem_node.id);

            uppy = setup_uppy_for_upload_button(
                elem_node, tus_endpoint, model_verification_endpoint, refresh_model_list_when_upload_complete_wrapper(elem_node.getAttribute("tabname")));
            uppy_object_map.set(elem_node.id, uppy);

        } else {
            const uppy = setup_uppy_for_upload_button(
                elem_node, tus_endpoint, model_verification_endpoint, refresh_model_list_when_upload_complete_wrapper(elem_node.getAttribute("tabname")));

            uppy_object_map.set(elem_node.id, uppy);
        }

    }

    window.register_button = register_button;

    onUiLoaded(() => {
        var buttons = gradioApp().querySelectorAll('.model-upload-button');
        buttons.forEach(register_button);
        var observeUploadButtonChange = new MutationObserver((mutationList, observer) => {
            mutationList.forEach((item) => {
                var button = item.target.querySelector(".model-upload-button");
                if (button){
                    register_button(button);
                }
            });
        });
        observeUploadButtonChange.observe( gradioApp().querySelector('#txt2img_extra_tabs'), { childList:true, subtree:true });
        observeUploadButtonChange.observe( gradioApp().querySelector('#img2img_extra_tabs'), { childList:true, subtree:true });
    });
}
