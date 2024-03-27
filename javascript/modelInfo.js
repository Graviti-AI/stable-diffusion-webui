function _alert(message) {
    notifier.alert(message);
    throw message;
}

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
                values: (getArg) => {
                    const arg = getArg("hr_checkpoint_name");
                    return typeof arg === "object" ? arg : [arg];
                },
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
        for (let axis of ["Z", "Y", "X"]) {
            keys.push({
                source: "xyz_plot",
                flag: (getArg) =>
                    getArg("Script:script_list:") === "X/Y/Z plot" &&
                    getArg(
                        `X/Y/Z plot:${axis} type:script_${mode}_xyz_plot_${axis.toLowerCase()}_type`,
                    ) === "Prompt S/R",
                values: (getArg) => {
                    const input = _parseCSV(
                        getArg(
                            `X/Y/Z plot:X values:script_${mode}_xyz_plot_${axis.toLowerCase()}_values`,
                        ),
                    )[0].map((item) => item.trim());

                    const src = input[0];
                    const dsts = input.slice(1);
                    const results = [];

                    [getArg("prompt"), getArg("negative_prompt")]
                        .filter(Boolean)
                        .forEach((prompt) => {
                            results.push(...dsts.map((dst) => prompt.replaceAll(src, dst)));
                        });
                    return results;
                },
            });
        }
        prompt_keys[mode] = keys;
    }
    return prompt_keys;
}

const _CHECKPOINT_KEYS = _get_checkpoint_keys();
const _PROMPT_KEYS = _get_promot_keys();
const _REQUEST_FAILED = "REQUEST FAILED";
const _NETWORK_REG = /<(\w+):([^>]+)>/g;
const _SIGNATURE = {
    start: "signature(",
    end: ")",
};

function _getValue(item) {
    return item.value;
}

function _getStem(filename) {
    const index = filename.lastIndexOf(".");
    if (index === -1) {
        return filename;
    }
    return filename.slice(0, index);
}

function _parseCSV(data, delimiter, newline) {
    delimiter = delimiter || ",";
    newline = newline || "\n";
    const n_sep = "\x1D";
    const q_sep = "\x1E";
    const c_sep = "\x1F";
    const n_sep_reg = new RegExp(n_sep, "g");
    const q_sep_reg = new RegExp(q_sep, "g");
    const c_sep_reg = new RegExp(c_sep, "g");
    const field_reg = new RegExp(
        `(?<=(^|[${delimiter}\\n]))"(|[\\s\\S]+?(?<![^"]"))"(?=($|[${delimiter}\\n]))`,
        "g",
    );

    return data
        .replace(/\r/g, "")
        .replace(/\n+$/, "")
        .replace(field_reg, (_, __, p2) =>
            p2.replace(/\n/g, n_sep).replace(/""/g, q_sep).replace(/,/g, c_sep),
        )
        .split(/\n/)
        .map((line) =>
            line
                .split(delimiter)
                .map((cell) =>
                    cell
                        .replace(n_sep_reg, newline)
                        .replace(q_sep_reg, '"')
                        .replace(c_sep_reg, ","),
                ),
        );
}

function _findLast(array, callbackFn) {
    if (typeof array.findLast === "function") {
        return array.findLast(callbackFn);
    }
    for (let item of PYTHON.reversed(array)) {
        if (callbackFn(item)) {
            return item;
        }
    }
    return undefined;
}

function _convertModelInfo(model_info, source) {
    return {
        model_type: model_info.model_type,
        source: source,
        name: model_info.name,
        sha256: model_info.sha256,
        config_sha256: model_info.config_sha256,
    };
}

async function _listCandidateModels(all_model_names) {
    const params = new URLSearchParams();
    for (let [model_type, model_names] of Object.entries(all_model_names)) {
        model_names.forEach((model_name) => params.append(model_type, model_name));
    }
    const url = `/internal/candidate_models?${params.toString()}`;
    try {
        const response = await fetchGet(url);
        if (!response.ok) {
            console.error(
                `Request candidate models failed, url: "${url}", reason: "${response.status} ${response.statusText}"`,
            );
            throw _REQUEST_FAILED;
        }
        const content = await response.json();
        return content.models;
    } catch (error) {
        console.error(`Request candidate models failed due to exception, url: "${url}"`);
        console.error(error);
        throw _REQUEST_FAILED;
    }
}

function _buildModelTree(models) {
    const results = {
        checkpoint: {},
        embedding: {},
        hypernetwork: {},
        lora: {},
        lycoris: {},
    };
    for (let model of models) {
        const model_type = model.model_type;
        const key =
            model_type === "checkpoint"
                ? `${model.name} [${model.sha256.slice(0, 10)}]`
                : _getStem(model.name);

        results[model_type][key] = model;
    }
    return results;
}

function _getModel(model_tree, model_type, key) {
    const model = model_tree[model_type][key.value];
    if (!model) {
        _alert(`${model_type} model "${key.value}" not found in your workspace`);
    }
    return _convertModelInfo(model, key.source);
}

function _findExtraNetworkModelKeys(prompts) {
    const network_keys = {
        lora: [],
        lyco: [],
        hypernet: [],
    };

    for (let prompt of prompts) {
        const results = prompt.value.matchAll(_NETWORK_REG);
        for (let result of results) {
            let type = result[1];
            const keys = network_keys[type];
            if (!keys) {
                _alert(`Unknown network type "${type}"`);
            }

            const key = result[2].split(":")[0];
            keys.push({ value: key, source: prompt.source });
        }
    }
    return network_keys;
}

function _findEmbeddingModels(model_tree, prompts) {
    const models = [];
    const processed_prompts = prompts.map((item) => ({
        value: item.value.replace(_NETWORK_REG, ""),
        source: item.source,
    }));

    for (let [key, model_info] of Object.entries(model_tree.embedding)) {
        const reg = new RegExp(`\\b${key}\\b`);

        for (let prompt of processed_prompts) {
            if (reg.test(prompt.value)) {
                models.push(_convertModelInfo(model_info, prompt.source));
                break;
            }
        }
    }
    return models;
}

function _getSignature(args) {
    const arg = _findLast(
        args,
        (item) =>
            typeof item === "string" &&
            item.startsWith(_SIGNATURE.start) &&
            item.endsWith(_SIGNATURE.end),
    );
    if (!arg) {
        _alert("signature not found in the arguments");
    }
    return JSON.parse(arg.slice(_SIGNATURE.start.length, -_SIGNATURE.end.length));
}

function _getAllModelInfo(checkpoint_titles, prompts, network_keys, model_tree) {
    const all_keys = {
        checkpoint: checkpoint_titles,
        lora: network_keys.lora,
        lycoris: network_keys.lyco,
        hypernetwork: network_keys.hypernet,
    };
    const all_model_info = [];

    for (let [model_type, keys] of Object.entries(all_keys)) {
        for (let key of keys) {
            all_model_info.push(_getModel(model_tree, model_type, key));
        }
    }

    const embedding_models = _findEmbeddingModels(model_tree, prompts);
    all_model_info.push(...embedding_models);

    return all_model_info;
}

async function getAllModelInfo(mode, args) {
    const signature = _getSignature(args);
    const index = signature.indexOf("all_model_info");
    if (index === -1) {
        _alert('"all_model_info" not found in signature');
    }

    const getArg = (key) => args[signature.indexOf(key)];

    let checkpoint_titles = [];
    const prompts = [];

    for (let key_info of _CHECKPOINT_KEYS[mode]) {
        if (key_info.flag(getArg)) {
            checkpoint_titles.push(
                ...key_info
                    .values(getArg)
                    .filter(Boolean)
                    .map((item) => ({ value: item, source: key_info.source })),
            );
        }
    }
    checkpoint_titles = checkpoint_titles.filter(
        (title) => title.value && title.value !== "Use same checkpoint",
    );

    for (let key_info of _PROMPT_KEYS[mode]) {
        if (key_info.flag(getArg)) {
            prompts.push(
                ...key_info
                    .values(getArg)
                    .filter(Boolean)
                    .map((item) => ({ value: item.trim(), source: key_info.source }))
                    .filter((item) => item.value),
            );
        }
    }

    const network_keys = _findExtraNetworkModelKeys(prompts);
    const all_model_names = {
        checkpoint: checkpoint_titles.map((item) => _getStem(_getValue(item).split(" [")[0])),
        hypernetwork: network_keys.hypernet.map(_getValue),
        lora: network_keys.lora.map(_getValue),
        lycoris: network_keys.lyco.map(_getValue),
    };

    try {
        const candidate_models = await _listCandidateModels(all_model_names);
        const model_tree = _buildModelTree(candidate_models);
        const all_model_info = _getAllModelInfo(
            checkpoint_titles,
            prompts,
            network_keys,
            model_tree,
        );
        return [index, JSON.stringify(all_model_info)];
    } catch (error) {
        if (error === _REQUEST_FAILED) {
            console.error('Set "all_model_info" to null due to request fail');
            return [index, null];
        }
        throw error;
    }
}
