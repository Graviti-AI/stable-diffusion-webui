let featurePermissions = null;

function _getControlNetArgNames() {
    const arg_names = {};
    for (let tabname of ["txt2img", "img2img"]) {
        const names = [];
        for (let i of PYTHON.range(4)) {
            names.push({
                enable: `ControlNet:Enable:${tabname}_controlnet_ControlNet-${i}_controlnet_enable_checkbox`,
                preprocessor: `ControlNet:Preprocessor:${tabname}_controlnet_ControlNet-${i}_controlnet_preprocessor_dropdown`,
                model: `ControlNet:Model:${tabname}_controlnet_ControlNet-${i}_controlnet_model_dropdown`,
            });
        }
        arg_names[tabname] = names;
    }
    return arg_names;
}

let _controlNetArgNames = _getControlNetArgNames();

async function _getFeaturePermissions() {
    if (!featurePermissions) {
        const response = await fetchGet("/config/feature_permissions");
        const body = await response.json();
        featurePermissions = {
            generate: body.generate,
            buttons: Object.fromEntries(body.buttons.map((item) => [item.name, item])),
        };
    }
    return featurePermissions;
}

function joinWords(words, conjunction = "and") {
    const names = words.map((item) => `"${item}"`);
    if (names.length == 1) {
        return names[0];
    }
    const last_name = names.pop();
    return `${names.join(", ")} ${conjunction} ${last_name}`;
}

function _joinTiers(tiers) {
    const unique_tiers = [];
    for (let tier of ["Basic", "Plus", "Pro", "Api"]) {
        if (tiers.includes(tier)) {
            unique_tiers.push(tier);
        }
    }
    return joinWords(unique_tiers, "or");
}

function _checkControlNetXL(tabname, args) {
    const names = _controlNetArgNames[tabname];
    const signature = getSignatureFromArgs(args);
    const getArg = (key) => args[signature.indexOf(key)];
    for (let name of names) {
        if (!getArg(name.enable)) {
            continue;
        }
        if (getArg(name.preprocessor).toLowerCase().includes("revision")) {
            return false;
        }
        if (getArg(name.model).toLowerCase().includes("xl")) {
            return false;
        }
    }
    return true;
}

function _tierCheckFailed(features, allowed_tiers) {
    const features_message = joinWords(features);
    const allowed_tiers_message = _joinTiers(allowed_tiers);
    const list_name = `${features.join("_").toLowerCase()}_tier_checker`;

    addPopupGtagEvent(SUBSCRIPTION_URL, list_name);
    notifier.confirm(
        `${features_message} is not available in the current plan. Please upgrade to ${allowed_tiers_message} to use it.`,
        () => {
            addUpgradeGtagEvent(SUBSCRIPTION_URL, list_name);
            window.open(SUBSCRIPTION_URL, "_blank");
        },
        () => {},
        {
            labels: {
                confirm: "Upgrade Now",
                confirmOk: "Upgrade",
            },
        },
    );
    throw `${features_message} is not available for current tier.`;
}

async function tierCheckGenerate(tabname, args) {
    const features = [];
    const allowed_tiers = [];
    let is_order_info_requested = false;

    const permissions = await _getFeaturePermissions();
    for (let permission of permissions.generate) {
        if (permission.allowed_tiers.includes(userTier)) {
            continue;
        }
        if (!is_order_info_requested) {
            await updateOrderInfo();
            is_order_info_requested = true;
            if (permission.allowed_tiers.includes(userTier)) {
                continue;
            }
        }

        if (permission.name === "ControlNetXL") {
            if (_checkControlNetXL(tabname, args)) {
                continue;
            }
        } else {
            const elem_id = permission[`${tabname}_id`];
            const tab_elem_id = `tab_${tabname}`;
            if (permission.type === "checkbox") {
                const target_elem = document.querySelector(`#${tab_elem_id} #${elem_id} input`);
                if (target_elem.checked === permission.value) {
                    continue;
                }
            } else if (permission.type === "dropdown") {
                const target_elem = document.querySelector(`#${tab_elem_id} #${elem_id} input`);
                if (target_elem.value === permission.value) {
                    continue;
                }
            } else {
                continue;
            }
        }
        features.push(permission.name);
        allowed_tiers.push(...permission.allowed_tiers);
    }

    if (features.length == 0) {
        return;
    }
    _tierCheckFailed(features, allowed_tiers);
}

async function tierCheckButtonInternal(feature_name) {
    const permissions = await _getFeaturePermissions();
    const permission = permissions.buttons[feature_name];

    if (permission.allowed_tiers.includes(userTier)) {
        return;
    }
    await updateOrderInfo();
    if (permission.allowed_tiers.includes(userTier)) {
        return;
    }
    _tierCheckFailed([feature_name], permission.allowed_tiers);
}

function tierCheckButton(feature_name) {
    return async (...args) => {
        await tierCheckButtonInternal(feature_name);
        return args;
    };
}
