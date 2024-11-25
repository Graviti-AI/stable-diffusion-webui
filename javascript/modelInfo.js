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
                        `Detection and Inpainting Tool (ADetailer):Use separate checkpoint:script_${mode}_adetailer_ad_use_checkpoint`,
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
                        `Detection and Inpainting Tool (ADetailer):Use separate checkpoint 2nd:script_${mode}_adetailer_ad_use_checkpoint_2nd`,
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
                            `X/Y/Z plot:${axis} values:script_${mode}_xyz_plot_${axis.toLowerCase()}_values`,
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

function getStem(filename) {
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
        id: model_info.id,
        model_type: model_info.model_type,
        base: model_info.base,
        source: source,
        name: model_info.filename,
        sha256: model_info.sha256,
        config_sha256: model_info.config_sha256,
    };
}

async function _listCandidateModels(all_model_names, prompts) {
    const params = new URLSearchParams();

    prompts.forEach((prompt) => params.append("prompt", prompt.value));
    for (let [model_type, model_names] of Object.entries(all_model_names)) {
        model_names.forEach((model_name) => params.append(model_type.toLowerCase(), model_name));
    }

    const url = `/gallery-api/v1/candidate-models?${params.toString()}`;
    try {
        const response = await fetchGet(url);
        if (!response.ok) {
            console.error(
                `Request candidate models failed, url: "${url}", reason: "${response.status} ${response.statusText}"`,
            );
            throw _REQUEST_FAILED;
        }
        const content = await response.json();

        const results = content.items;
        return results;
    } catch (error) {
        console.error(`Request candidate models failed due to exception, url: "${url}"`);
        console.error(error);
        throw _REQUEST_FAILED;
    }
}

function _buildModelTree(models) {
    const results = {
        CHECKPOINT: {},
        EMBEDDING: {},
        HYPERNETWORK: {},
        LORA: {},
    };
    for (let model of models) {
        const model_type = model.model_type === "LYCORIS" ? "LORA" : model.model_type;
        const key =
            model_type === "CHECKPOINT"
                ? `${model.filename} [${model.sha256.slice(0, 10)}]`
                : getStem(model.filename);

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
    return {
        LORA: [...network_keys.lora, ...network_keys.lyco],
        HYPERNETWORK: network_keys.hypernet,
    };
}

function _findEmbeddingModels(model_tree, prompts) {
    const models = [];
    const processed_prompts = prompts.map((item) => ({
        value: item.value.replace(_NETWORK_REG, ""),
        source: item.source,
    }));

    for (let [key, model_info] of Object.entries(model_tree.EMBEDDING)) {
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

function getSignatureFromArgs(args) {
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
        CHECKPOINT: checkpoint_titles,
        LORA: network_keys.LORA,
        HYPERNETWORK: network_keys.HYPERNETWORK,
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

async function getAllModelInfo(mode, args, all_style_info) {
    const signature = getSignatureFromArgs(args);
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

    if (all_style_info) {
        for (let style of all_style_info) {
            if (style.prompt) {
                prompts.push({ value: style.prompt, source: "style" });
            }
            if (style.negative_prompt) {
                prompts.push({ value: style.negative_prompt, source: "style" });
            }
        }
    }

    return [index, await getAllModelInfoByCheckpointsAndPrompts(checkpoint_titles, prompts)];
}

async function getAllModelInfoByCheckpointsAndPrompts(checkpoint_titles, prompts) {
    const network_keys = _findExtraNetworkModelKeys(prompts);
    const all_model_names = {
        CHECKPOINT: checkpoint_titles.map((item) => getStem(_getValue(item).split(" [")[0])),
        HYPERNETWORK: network_keys.HYPERNETWORK.map(_getValue),
        LORA: network_keys.LORA.map(_getValue),
    };

    try {
        const candidate_models = await _listCandidateModels(all_model_names, prompts);
        const model_tree = _buildModelTree(candidate_models);
        const all_model_info = _getAllModelInfo(
            checkpoint_titles,
            prompts,
            network_keys,
            model_tree,
        );
        return all_model_info;
    } catch (error) {
        if (error === _REQUEST_FAILED) {
            console.error('Set "all_model_info" to null due to request fail');
            return null;
        }
        throw error;
    }
}

function _getLastLine(text) {
    const index = text.lastIndexOf("\n");
    if (index === -1) {
        return text;
    }

    return text.slice(index + 1);
}

function _splitModelTitle(title) {
    const sep = " [";
    const index = title.lastIndexOf(sep);

    if (index === -1 || index === 0 || index === title.length - 1) {
        throw "Failed to parse the model title";
    }
    const stem = title.slice(0, index);
    const sha256 = title.slice(index + sep.length).replace("]", "");

    return [stem, sha256];
}

function _splitHashes(input) {
    if (input.startsWith('"') && input.endsWith('"')) {
        input = input.slice(1, -1);
    }
    return input.split(",");
}

const _PATTERN = /\s*(\w[\w \-/]+):\s*("(?:\\.|[^\\"])+"|[^,]*)(?:,|$)/;
const _CONFIGS = [
    {
        type: "CHECKPOINT",
        source: null,
        flag: (params) => params["Model hash"],
        values: (params) => [`${params["Model"] ? params["Model"] : ""}: ${params["Model hash"]}`],
    },
    {
        type: "CHECKPOINT",
        source: "refiner",
        flag: (params) => params["Refiner"],
        values: (params) => {
            const [stem, sha256] = _splitModelTitle(params["Refiner"]);
            return [`${stem}:${sha256}`];
        },
    },
    {
        type: "LORA",
        source: null,
        flag: (params) => params["Lora hashes"],
        values: (params) => _splitHashes(params["Lora hashes"]),
    },
    {
        type: "HYPERNETWORK",
        source: null,
        flag: (params) => params["Hypernetwork hashes"],
        values: (params) => _splitHashes(params["Hypernetwork hashes"]),
    },
    {
        type: "EMBEDDING",
        source: null,
        flag: (params) => params["TI hashes"],
        values: (params) => _splitHashes(params["TI hashes"]),
    },
];

function _findall(pattern, text) {
    const regex = new RegExp(pattern, "g");
    const results = [];

    let match;

    while ((match = regex.exec(text)) !== null) {
        if (match.length > 1) {
            results.push(match.slice(1));
        } else {
            results.push([match[0]]);
        }
    }

    return results;
}

function _parsePNGInfo(pnginfo) {
    const line = _getLastLine(pnginfo.trim());
    return Object.fromEntries(_findall(_PATTERN, line));
}

function _parseParams(params) {
    const results = {
        CHECKPOINT: [],
        LORA: [],
        EMBEDDING: [],
        HYPERNETWORK: [],
    };

    for (const config of _CONFIGS) {
        if (config.flag(params)) {
            results[config.type].push(...config.values(params));
        }
    }

    return results;
}

async function _listCandidateModelsByHash(hashes) {
    const params = new URLSearchParams();

    for (let [model_type, values] of Object.entries(hashes)) {
        values.forEach((value) => params.append(model_type.toLowerCase(), value));
    }

    const url = `/gallery-api/v1/candidate-models-by-hash?${params.toString()}`;
    try {
        const response = await fetchGet(url);
        if (!response.ok) {
            console.error(
                `Request candidate models by hash failed, url: "${url}", reason: "${response.status} ${response.statusText}"`,
            );
            throw _REQUEST_FAILED;
        }
        const content = await response.json();

        const results = content.items;
        return results;
    } catch (error) {
        console.error(`Request candidate models failed due to exception, url: "${url}"`);
        console.error(error);
        throw _REQUEST_FAILED;
    }
}

function _filterModelWithStatus(models, from_gallery) {
    const results = [];

    for (const model of models) {
        const prefix = from_gallery
            ? `${model.info.model_type} model "${getStem(model.info.filename)}"`
            : `${model.model_type} model "${model.stem} [${model.sha256}]"`;

        switch (model.status) {
            case "NOTFOUND":
                notifier.alert(`${prefix} not found in the Gallery`);
                continue;

            case "DELETED":
                notifier.alert(`${prefix} is a deleted model`);
                continue;

            case "UNPUBLISHED":
                notifier.alert(`${prefix} is a unpublished model`);
                continue;

            case "OK":
                if (model.info.favorited_at === null) {
                    notifier.warning(`${prefix} not found in your favorites`);
                } else {
                    results.push(model.info);
                }
                continue;
            default:
                throw `Unknown model status: "${model.status}"`;
        }
    }
    return results;
}

async function _getAllModelInfoFromPNGInfo(pnginfo) {
    const params = _parsePNGInfo(pnginfo);
    const hashes = _parseParams(params);

    const models = Object.values(hashes).every((item) => item.length === 0)
        ? []
        : await _listCandidateModelsByHash(hashes);

    return _filterModelWithStatus(models, false);
}

function _getRunModelInfo(models) {
    const filtered_models = _filterModelWithStatus(models, true);
    return filtered_models.map((item) => ({
        id: item.id,
        model_type: item.model_type,
        base: item.base,
        name: item.filename,
        sha256: item.sha256,
        config_sha256: item.config_sha256,
    }));
}

async function extractModelsFromPnginfo() {
    const res = Array.from(arguments);

    if (gallery_run_pnginfo !== null && gallery_run_models !== null) {
        try {
            res[0] = gallery_run_pnginfo;
            res[1] = JSON.stringify(_getRunModelInfo(gallery_run_models));
        } finally {
            gallery_run_pnginfo = null;
            gallery_run_models = null;
        }
        return res;
    }

    const pnginfo = res[0];
    const all_model_info = await _getAllModelInfoFromPNGInfo(pnginfo);
    all_model_info.forEach((item) => {
        item.name = item.filename;
        delete item.filename;
    });
    res[1] = JSON.stringify(all_model_info);

    return res;
}

async function _queryTaskResult(task_id) {
    const url = `/gallery-api/v1/tasks/${task_id}/progresses`;
    while (true) {
        const response = await fetchGet(url);
        if (!response.ok) {
            throw `Falied to query task progress: "${response.status} ${response.statusText}"`;
        }

        const content = await response.json();

        switch (content.status) {
            case "QUEUED":
                await PYTHON.asyncio.sleep(2000);
                break;

            case "PREPARING":
            case "RUNNING":
                break;

            case "FAILED":
                throw `Failed to import model from Civitai: ${content.message}`;

            case "SUCCESS":
                return content.result;

            default:
                throw `Unknown progress status: "${content.status}"`;
        }

        await PYTHON.asyncio.sleep(1000);
    }
}

async function _queryModelId(sha256) {
    const url = `/gallery-api/v1/models?sha256=${sha256}`;

    for (let i = 0; i < 200; i++) {
        const response = await fetchGet(url);
        if (!response.ok) {
            throw `Failed to get model: "${response.status} ${response.statusText}"`;
        }

        const content = await response.json();

        if (content.items.length === 0) {
            await PYTHON.asyncio.sleep(3000);
        }
        return content.items[0].id;
    }

    throw "Failed to get model: timeout";
}

async function _addFavoriteModel(model_id) {
    const response = await fetchPost({
        url: "/gallery-api/v1/favorites/models",
        data: { ids: [model_id] },
    });
    if (!response.ok) {
        throw `Failed to add favorite model: "${response.status} ${response.statusText}"`;
    }

    const content = await response.json();

    return content.items.length > 0;
}

async function _checkModelURLFromCivitai() {
    const params = new URLSearchParams(location.search);
    const sha256 = params.get("hash");
    if (!sha256) {
        return;
    }

    switch_to_txt2img();

    const response = await fetchPost({
        url: "/gallery-api/v1/tasks",
        data: { sha256: sha256, auto_register: true },
    });
    if (!response.ok) {
        throw `Failed to check civitai model: "${response.status} ${response.statusText}"`;
    }

    const result = await response.json();
    switch (result.status) {
        case "MODEL_EXISTS":
            model = result.models[0];
            if (await _addFavoriteModel(model.id)) {
                notifier.success(
                    `Successfully add civitai model (${sha256.slice(0, 10)}) to your favorite.`,
                );
            }
            if (model.model_type === "CHECKPOINT") {
                galleryApp.setCheckpoint(model.filename, model.sha256);
            } else {
                galleryApp.setExtraNetwork(model.model_type, model.filename);
            }
            return;

        case "TASK_EXISTS":
        case "TASK_CREATED":
            notifier.warning(
                `Model (${sha256.slice(0, 10)}) in our gallery. Importing it from Civitai now, it could take up to 5 minutes. Meanwhile, feel free to check out thousands of models already in our galery.`,
            );

            const task_result = await _queryTaskResult(result.task_id);
            model_id = task_result.model_id;
            if (!model_id) {
                model_id = await _queryModelId(task_result.sha256);
            }

            if (await _addFavoriteModel(model_id)) {
                notifier.success(
                    `Successfully add civitai model (${sha256.slice(0, 10)}) to your favorite. You can use it from the gallery`,
                );
            }
            return;

        case "UNSUPPORTED":
            throw `Failed to import model from Civitai: ${result.message}`;

        case "INVALID_INFO":
            throw `Failed to import model from Civitai: ${result.message}. Please import it in model gallery manually.`;

        case "BINARY_EXISTS":
        case "UPLOAD_REQUIRED":
            throw `Failed to import model from Civitai: invalid status "${model.status}"`;

        default:
            throw `Failed to import model from Civitai: unknown status: "${model.status}"`;
    }
}

async function checkModelURLFromCivitai() {
    try {
        await _checkModelURLFromCivitai();
    } catch (error) {
        notifier.alert(error);
        throw error;
    }
}
