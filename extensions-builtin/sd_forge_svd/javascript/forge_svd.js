async function submit_svd_task() {
    addGenerateGtagEvent("#svd_generate_button > span", "svd_generate_button");
    await tierCheckButtonInternal("SVD");

    const res = Array.from(arguments);
    res[0] = randomId();

    return res;
}

onUiLoaded(async function () {
    const tab_name = "svd_interface";
    systemMonitorState[tab_name] = {
        generate_button_id: "svd_generate_button",
        timeout_id: null,
        functions: {
            "extensions.svd": {
                params: {
                    width: 1024,
                    height: 576,
                    steps: 20,
                    frames: 14,
                    coefficient: 2,
                },
                link_params: {}, // tab_name: function_name
                mutipliers: {}, // multipler_name: value
                link_mutipliers: {}, // function_name: param_name
            },
        },
    };
    await updateButton(tab_name);
});
