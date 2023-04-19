import { setup_uppy_for_upload_button } from "/public/js/upply.mjs"

if (typeof setup_uppy_for_upload_button != "undefined") {
    const tus_endpoint = '/files';
    const model_verification_endpoint= '/verify-model-existence';
    const uppy_object_map = new Map();

    function register_button(elem_node){
        if (uppy_object_map.has(elem_node.id))
        {
            var uppy = uppy_object_map.get(elem_node.id);
            uppy.close();
            uppy = null;
            uppy_object_map.delete(elem_node.id)

            setTimeout(() =>{
                const uppy = setup_uppy_for_upload_button(elem_node, tus_endpoint, model_verification_endpoint);

                uppy_object_map.set(elem_node.id, uppy);
            }, 200);

        } else {
            const uppy = setup_uppy_for_upload_button(elem_node, tus_endpoint, model_verification_endpoint);

            uppy_object_map.set(elem_node.id, uppy);
        }

    }

    window.register_button = register_button;

    onUiLoaded(() => {
        var buttons = gradioApp().querySelectorAll('.model-upload-button');
        buttons.forEach(register_button);
    });
}
