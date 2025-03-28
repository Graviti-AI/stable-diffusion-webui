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

async function tierCheckFlux(all_model_info) {
    if (all_model_info.every((item) => item.base !== "FLUX")) {
        return;
    }
    const featurePermissions = getDiffusApp().featurePermissions;
    featurePermissions.checkTierForButton("Flux");
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
    await _checkSafetyAgreement(getArg, featurePermissions);
}

function tierCheckButton(feature_name) {
    return async (...args) => {
        const featurePermissions = getDiffusApp().featurePermissions;
        featurePermissions.checkTierForButton(feature_name);

        return args;
    };
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
    if (!upgrade_info.need_upgrade) {
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

const _SAFETY_AGREEMENT_KEY = "safety_agreement_agreed";
let _dirtyWords = null;

async function _getSafetyAgreement() {
    const params = new URLSearchParams({ field: _SAFETY_AGREEMENT_KEY });
    const url = `/api/user_profile?${params.toString()}`;

    const response = await fetchGet(url);
    if (!response.ok) {
        throw `Get safety agreement agreed failed: ${response.statusText}`;
    }
    const content = await response.json();

    return content[_SAFETY_AGREEMENT_KEY];
}

async function _setSafetyAgreement() {
    const url = "/api/user_profile";
    const body = {};
    body[_SAFETY_AGREEMENT_KEY] = true;

    const response = await fetch(url, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });

    if (!response.ok) {
        throw `Set safety agreement agreed failed: ${response.statusText}`;
    }
    return await response.json();
}

async function _getDirtyWords() {
    if (!_dirtyWords) {
        const response = await fetchGet("/public/dirty_words.txt");
        if (!response.ok) {
            throw `Request dirty words failed: ${response.statusText}`;
        }
        const body = await response.text();

        const lines = body.toLowerCase().split(/[\r\n]+/);

        _dirtyWords = [...new Set(lines)];
    }
    return _dirtyWords;
}

async function _checkPromptDirtyWords(prompt) {
    prompt = prompt.toLowerCase();

    const words_1 = prompt.split(/\W+/).filter(Boolean);
    const words_2 = prompt.split(/[\s,]+/).filter(Boolean);

    const words = new Set([...words_1, ...words_2]);
    if (words.size === 0) {
        return false;
    }

    const dirty_words = await _getDirtyWords();

    let results = dirty_words.filter((word) => words.has(word));

    return results.length > 0;
}

async function _checkSafetyAgreement(getArg, permissions) {
    const tier = realtimeData.orderInfo.tier;

    if (!permissions.features.PrivateImage.allowed_tiers.includes(tier)) {
        return;
    }
    if (window.Cookies.get(_SAFETY_AGREEMENT_KEY)) {
        return;
    }

    if (await _getSafetyAgreement()) {
        window.Cookies.set(_SAFETY_AGREEMENT_KEY, true, { expires: 360 });
        return;
    }

    if (!(await _checkPromptDirtyWords(getArg("prompt")))) {
        return;
    }

    const message = `
        <br/>
        <p>
            Potential Not Safe For Work (NSFW) content detected in the prompt. To continue, you must
            acknowledge and agree to our terms. By clicking <b>I Agree</b>, you confirm that you
            meet the following criteria and will use the content responsibly in accordance with our
            policies.
        </p>
        <br/>
        <p>
            <input id="awn-checkbox-1" type="checkbox" />
            <label>
                I am at least 18 years old or of legal age in my jurisdiction
            </label>
        </p>
        <p>
            <input id="awn-checkbox-2" type="checkbox" />
            <label>
                I have read and agree to Diffus's
                <a
                    href="https://www.diffus.me/safety/"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    Safety Agreement
                </a>
            </label>
        </p>
    `;

    let is_agreed = null;

    const confirm_modal = notifier.confirm(
        message,
        () => {
            is_agreed = true;
        },
        () => {
            is_agreed = false;
        },
        {
            labels: {
                confirm: "Safety Agreement",
                confirmOk: "I Agree",
            },
        },
    );

    const checkbox_1 = confirm_modal.el.querySelector("#awn-checkbox-1");
    const checkbox_2 = confirm_modal.el.querySelector("#awn-checkbox-2");

    function _updateButtonStatus() {
        if (checkbox_1.checked && checkbox_2.checked) {
            confirm_modal.okBtn.disabled = false;
            confirm_modal.okBtn.style.opacity = "";
            confirm_modal.okBtn.style.cursor = "";
        } else {
            confirm_modal.okBtn.disabled = true;
            confirm_modal.okBtn.style.opacity = 0.35;
            confirm_modal.okBtn.style.cursor = "not-allowed";
        }
    }

    checkbox_1.addEventListener("change", _updateButtonStatus);
    checkbox_2.addEventListener("change", _updateButtonStatus);

    _updateButtonStatus();

    while (is_agreed === null) {
        await PYTHON.asyncio.sleep(200);
    }

    if (is_agreed) {
        await _setSafetyAgreement();
        window.Cookies.set(_SAFETY_AGREEMENT_KEY, true, { expires: 360 });
        return;
    }

    throw "Safety Agreement has not been agreed";
}
