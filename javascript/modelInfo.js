function _get_checkpoint_keys() {
    const checkpoint_keys = {};
    for (let mode of ["txt2img", "img2img"]) {
        const keys = [
            {
                source: null,
                flag: (getArg) => true,
                values: (getArg) => [getArg("model_title")],
            },
            {
                source: "hr",
                flag: (getArg) => getArg("enable_hr"),
                values: (getArg) => [getArg("hr_checkpoint_name")],
            },
            {
                source: "refiner",
                flag: (getArg) => getArg(`Refiner:Refiner:${mode}_enable-checkbox`),
                values: (getArg) => [getArg(`Refiner:Checkpoint:${mode}_checkpoint`)],
            },
            {
                source: "adetailer",
                flag: (getArg) =>
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):Enable ADetailer:script_${mode}_adetailer_ad_enable`,
                    ) &&
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):ADetailer model:script_${mode}_adetailer_ad_model`,
                    ) != "None" &&
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):Use separate checkpoint (experimental):script_${mode}_adetailer_ad_use_checkpoint`,
                    ),
                values: (getArg) => [
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):ADetailer checkpoint:script_${mode}_adetailer_ad_checkpoint`,
                    ),
                ],
            },
            {
                source: "adetailer",
                flag: (getArg) =>
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):Enable ADetailer:script_${mode}_adetailer_ad_enable`,
                    ) &&
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):ADetailer model 2nd:script_${mode}_adetailer_ad_model_2nd`,
                    ) != "None" &&
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):Use separate checkpoint (experimental) 2nd:script_${mode}_adetailer_ad_use_checkpoint_2nd`,
                    ),
                values: (getArg) => [
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):ADetailer checkpoint 2nd:script_${mode}_adetailer_ad_checkpoint_2nd`,
                    ),
                ],
            },
        ];
        for (let axis of ["Z", "Y", "X"]) {
            keys.push({
                source: "xyz_plot",
                flag: (getArg) =>
                    getArg("Script:script_list:") === "X/Y/Z plot" &&
                    getArg(
                        `X/Y/Z plot:${axis} type:script_${mode}_xyz_plot_${axis.toLowerCase()}_type`,
                    ) === "Checkpoint name",
                values: (getArg) => getArg(`X/Y/Z plot:${axis} values:`),
            });
        }
        checkpoint_keys[mode] = keys;
    }
    return checkpoint_keys;
}

function _get_promot_keys() {
    const prompt_keys = {};
    for (let mode of ["txt2img", "img2img"]) {
        const keys = [
            {
                source: null,
                flag: (getArg) => true,
                values: (getArg) => [getArg("prompt"), getArg("negative_prompt")],
            },
            {
                source: "adetailer",
                flag: (getArg) =>
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):Enable ADetailer:script_${mode}_adetailer_ad_enable`,
                    ) &&
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):ADetailer model:script_${mode}_adetailer_ad_model`,
                    ) != "None",
                values: (getArg) => [
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):ad_prompt:script_${mode}_adetailer_ad_prompt`,
                    ),
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):ad_negative_prompt:script_${mode}_adetailer_ad_negative_prompt`,
                    ),
                ],
            },
            {
                source: "adetailer",
                flag: (getArg) =>
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):Enable ADetailer:script_${mode}_adetailer_ad_enable`,
                    ) &&
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):ADetailer model 2nd:script_${mode}_adetailer_ad_model_2nd`,
                    ) != "None",
                values: (getArg) => [
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):ad_prompt 2nd:script_${mode}_adetailer_ad_prompt_2nd`,
                    ),
                    getArg(
                        `Detection and Inpainting Tool (ADetailer):ad_negative_prompt 2nd:script_${mode}_adetailer_ad_negative_prompt_2nd`,
                    ),
                ],
            },
            {
                source: "prompts_from_file_or_textbox",
                flag: (getArg) => getArg("Script:script_list:") === "Prompts from file or textbox",
                values: (getArg) =>
                    getArg(
                        "Prompts from file or textbox:List of prompt inputs:script_txt2img_prompts_from_file_or_textbox_prompt_txt",
                    ).split("\n"),
            },
        ];
        prompt_keys[mode] = keys;
    }
    return prompt_keys;
}

const _CHECKPOINT_KEYS = _get_checkpoint_keys();
const _PROMPT_KEYS = _get_promot_keys();
const _NETWORK_REG = /<(\w+):([^>]+)>/g;
const _SIGNATURE = {
    start: "signature(",
    end: ")",
};

function _convertModelInfo(model_info, source) {
    return {
        model_type: model_info.model_type === "lycoris" ? "lora" : model_info.model_type,
        source: source,
        name: model_info.name,
        sha256: model_info.sha256,
        config_sha256: model_info.config_sha256,
    };
}

function _listFavoriteModels(model_type) {
    return fetchGet(`/internal/favorite_models?model_type=${model_type}&page=1&page_size=100000`);
}

async function _getAllFavoriteModels() {
    const model_types = ["checkpoint", "embedding", "hypernetwork", "lora"];
    const results = await Promise.all(model_types.map((item) => _listFavoriteModels(item)));
    const favoriteModels = {};
    for (let [key, value] of PYTHON.zip(model_types, results)) {
        const response = await value.json();
        favoriteModels[key] = response.model_list;
    }
    return favoriteModels;
}

function _getAllFavoriteExtraNetworks(favoriteModels) {
    const type_mapping = {
        lora: "lora",
        hypernetwork: "hypernet",
    };
    const extra_networks = {
        lora: {},
        hypernet: {},
    };

    for (let [type, short_type] of Object.entries(type_mapping)) {
        for (let model_info of favoriteModels[type]) {
            extra_networks[short_type][model_info.name_for_extra] = model_info;
        }
    }
    return extra_networks;
}

function _findCheckpointModel(favoriteModels, title) {
    for (let model_info of favoriteModels.checkpoint) {
        if (model_info.title === title.value) {
            return _convertModelInfo(model_info, title.source);
        }
    }
    throw `SD checkpoint model "${title.value}" not found`;
}

function _findExtraNetworkModels(favoriteModels, prompts) {
    const favoriteExtraNetworks = _getAllFavoriteExtraNetworks(favoriteModels);
    const models = [];

    for (let prompt of prompts) {
        const results = prompt.value.matchAll(_NETWORK_REG);
        for (let result of results) {
            let type = result[1];
            if (type === "lyco") {
                type = "lora";
            }
            const name = result[2].split(":")[0];
            const extra_networks = favoriteExtraNetworks[type];
            if (!extra_networks) {
                throw `Unknown network type "${type}"`;
            }
            const model_info = extra_networks[name];
            if (!model_info) {
                throw `SD network "${name}" not found`;
            }
            models.push(_convertModelInfo(model_info, prompt.source));
        }
    }
    return models;
}

function _findEmbeddingModels(favoriteModels, prompts) {
    const models = [];
    const processed_prompts = prompts.map((item) => ({
        value: item.value.replace(_NETWORK_REG, ""),
        source: item.source,
    }));

    for (let model_info of favoriteModels.embedding) {
        const reg = new RegExp(`\\b${model_info.name_for_extra}\\b`);

        for (let prompt of processed_prompts) {
            if (reg.test(prompt.value)) {
                models.push(_convertModelInfo(model_info, prompt.source));
                break;
            }
        }
    }
    return models;
}

async function _getAllModelInfo(checkpoint_titles, prompts) {
    const favoriteModels = await _getAllFavoriteModels();
    const all_model_info = [];

    for (let checkpoint_title of checkpoint_titles) {
        if (!checkpoint_title.value || checkpoint_title.value === "Use same checkpoint") {
            continue;
        }
        all_model_info.push(_findCheckpointModel(favoriteModels, checkpoint_title));
    }

    const extra_networks = _findExtraNetworkModels(favoriteModels, prompts);
    all_model_info.push(...extra_networks);

    const embedding_models = _findEmbeddingModels(favoriteModels, prompts);
    all_model_info.push(...embedding_models);

    return all_model_info;
}

async function getAllModelInfo(mode, args) {
    const signature = getSignature(args);
    const index = signature.indexOf("all_model_info");
    if (index === -1) {
        throw "all_model_info not found in signature";
    }

    const getArg = (key) => args[signature.indexOf(key)];

    const checkpoint_titles = [];
    const prompts = [];

    for (let key_info of _CHECKPOINT_KEYS[mode]) {
        if (key_info.flag(getArg)) {
            checkpoint_titles.push(
                ...key_info
                    .values(getArg)
                    .map((item) => ({ value: item, source: key_info.source })),
            );
        }
    }

    for (let key_info of _PROMPT_KEYS[mode]) {
        if (key_info.flag(getArg)) {
            prompts.push(
                ...key_info
                    .values(getArg)
                    .map((item) => ({ value: item.trim(), source: key_info.source }))
                    .filter((item) => item.value),
            );
        }
    }

    const model_info = await _getAllModelInfo(checkpoint_titles, prompts);
    return [index, JSON.stringify(model_info)];
}

function getSignature(args) {
    const arg = args.findLast(
        (item) =>
            typeof item === "string" &&
            item.startsWith(_SIGNATURE.start) &&
            item.endsWith(_SIGNATURE.end),
    );
    if (!arg) {
        throw "signature not found";
    }
    return JSON.parse(arg.slice(_SIGNATURE.start.length, -_SIGNATURE.end.length));
}
