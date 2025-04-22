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

function _checkControlNetXL(tabname, getArg) {
    const names = _controlNetArgNames[tabname];
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

function _checkControlNetUnits(tabname, getArg, featurePermissions) {
    const names = _controlNetArgNames[tabname];
    const controlnet_units = names.map((item) => getArg(item.enable)).reduce((a, b) => a + b, 0);

    featurePermissions.checkControlNetUnitsLimit(controlnet_units);
}

function _checkSamplingSteps(tabname, getArg, featurePermissions) {
    const argName = `Sampler:Sampling steps:${tabname}_steps`;
    const steps = getArg(argName);

    featurePermissions.checkSamplingStepsLimit(steps);
}

function tierCheckButton(feature_name) {
    const featurePermissions = getDiffusApp().featurePermissions;
    featurePermissions.checkTierForButton(feature_name);
}

function tierCheckFlux(all_model_info) {
    if (all_model_info.every((item) => item.base !== "FLUX")) {
        return;
    }
    tierCheckButton("Flux");
}

async function tierCheckGenerate(tabname, args) {
    const names = [];

    const featurePermissions = getDiffusApp().featurePermissions;

    const signature = getSignatureFromArgs(args);
    const getArg = (key) => args[signature.indexOf(key)];

    for (const permission of featurePermissions.generate) {
        if (permission.name === "ControlNetXL") {
            if (_checkControlNetXL(tabname, getArg)) {
                continue;
            }
        } else {
            const elem_id = permission[`${tabname}_id`];
            const tab_elem_id = `tab_${tabname}`;
            if (permission.type === "checkbox") {
                const target_elem = document.querySelector(`#${tab_elem_id} #${elem_id} input`);
                if (!target_elem) {
                    continue;
                }
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
        names.push(permission.name);
    }

    featurePermissions.checkTierForGenerate(names);

    _checkSamplingSteps(tabname, getArg, featurePermissions);
    _checkControlNetUnits(tabname, getArg, featurePermissions);
    await featurePermissions.checkSafetyAgreement(getArg("prompt"));
}

function checkQueue(is_queued, textinfo) {
    if (!is_queued) {
        return false;
    }

    let result = textinfo.match(/^In queue\((\d+) ahead\)/);
    if (!result) {
        return false;
    }

    let ahead = Number(result[1]);

    const featurePermissions = getDiffusApp().featurePermissions;
    try {
        featurePermissions.checkFreeQueue(ahead);
    } catch (_) {
        return true;
    }
}

async function upgradeCheck(upgrade_info) {
    const itemName = idToItemNames[upgrade_info.id_task];
    if (itemName) {
        delete idToItemNames[upgrade_info.id_task];
    }

    if (!upgrade_info.need_upgrade) {
        const credits = upgrade_info.credits;
        if (itemName && typeof credits === "number") {
            getDiffusApp().analytics.reportSpendCreditsEvent(itemName, credits);
        }
        return;
    }

    const featurePermissions = getDiffusApp().featurePermissions;

    switch (upgrade_info.reason) {
        case "NSFW_CONTENT":
            featurePermissions.openNSFWContentDialog();
            return;

        case "INSUFFICIENT_CREDITS":
            featurePermissions.openInsufficientCreditsDialog();
            return;

        case "INSUFFICIENT_DAILY_CREDITS":
            featurePermissions.openInsufficientDailyCreditsDialog();
            return;

        case "REACH_CONCURRENCY_LIMIT":
            featurePermissions.openConcurrentTasksLimitDialog();
            return;

        default:
            throw `Unknown upgrade reason: "${upgrade_info.reason}".`;
    }
}
