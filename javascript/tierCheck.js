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

let _upgradableTiers = ["Basic", "Plus", "Pro", "Api"];
let _controlNetArgNames = _getControlNetArgNames();
let _featurePermissions = null;

const _AFFILIATE_PROGRAM =
    '<a href="/affiliate/everyone" target="_blank" style="text-wrap: nowrap">Affiliate Program</a>';

async function getFeaturePermissions() {
    if (!_featurePermissions) {
        const response = await fetchGet("/config/feature_permissions");
        const body = await response.json();

        _featurePermissions = {
            generate: body.generate,
            buttons: Object.fromEntries(body.buttons.map((item) => [item.name, item])),
            features: Object.fromEntries(body.features.map((item) => [item.name, item])),
            limits: Object.fromEntries(body.limits.map((item) => [item.tier, item])),
        };

        _featurePermissions.upgradablelimits = _upgradableTiers.map(
            (item) => _featurePermissions.limits[item],
        );
    }
    return _featurePermissions;
}

function _joinWords(words, conjunction = "and") {
    const names = words.map((item) => `"${item}"`);
    if (names.length == 1) {
        return names[0];
    }
    const last_name = names.pop();
    return `${names.join(", ")} ${conjunction} ${last_name}`;
}

function _joinTiers(tiers) {
    const unique_tiers = [];
    for (let tier of _upgradableTiers) {
        if (tiers.includes(tier)) {
            unique_tiers.push(tier);
        }
    }
    return _joinWords(unique_tiers, "or");
}

function _intersection(a, b) {
    return a.filter((item) => b.includes(item));
}

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

function _checkControlNetUnits(tabname, getArg, permissions, tier) {
    const names = _controlNetArgNames[tabname];
    const controlnet_units = names.map((item) => getArg(item.enable)).reduce((a, b) => a + b, 0);

    const current_limit = permissions.limits[tier];
    if (!current_limit) {
        throw `user tier "${tier}" not found in the "limits" of permissions.`;
    }

    const max_controlnet_units = current_limit.max_controlnet_units;

    if (controlnet_units <= max_controlnet_units) {
        return;
    }

    let message = `Your current plan allows for a maximum of ${max_controlnet_units} controlnet units.`;

    const higher_limits = permissions.upgradablelimits.filter(
        (item) => item.max_controlnet_units > max_controlnet_units,
    );
    if (higher_limits.length > 0) {
        message += " Upgrade to:";
        message += "<ul style='list-style: inside'>";
        for (let limit of higher_limits) {
            message += `<li><b>${limit.tier}</b> to increase your limit to \
                ${limit.max_controlnet_units} controlnet units;</li>`;
        }
        message += "</ul>";
    }

    addPopupGtagEvent(SUBSCRIPTION_URL, "controlnet_units_checker");
    notifier.confirm(
        message,
        () => {
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
    throw `The used controlnet units (${controlnet_units}) has exceeded the maximum limit (${max_controlnet_units}) for current tier.`;
}

function _checkSamplingSteps(tabname, getArg, permissions, tier) {
    const argName = `Sampler:Sampling steps:${tabname}_steps`;
    const steps = getArg(argName);

    const current_limit = permissions.limits[tier];
    if (!current_limit) {
        throw `user tier "${tier}" not found in the "limits" of permissions.`;
    }

    const max_sampling_steps = current_limit.max_sampling_steps;

    if (steps <= max_sampling_steps) {
        return;
    }

    let message = `Your current plan allows for a maximum of ${max_sampling_steps} sampling steps.`;

    const higher_limits = permissions.upgradablelimits.filter(
        (item) => item.max_sampling_steps > max_sampling_steps,
    );
    if (higher_limits.length > 0) {
        message += " Upgrade to:";
        message += "<ul style='list-style: inside'>";
        for (let limit of higher_limits) {
            message += `<li><b>${limit.tier}</b> to increase your limit to \
                ${limit.max_sampling_steps} sampling steps;</li>`;
        }
        message += "</ul>";
    }

    addPopupGtagEvent(SUBSCRIPTION_URL, "sampling_steps_checker");
    notifier.confirm(
        message,
        () => {
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
    throw `The used sampling steps (${steps}) has exceeded the maximum limit (${max_sampling_steps}) for current tier.`;
}

function _tierCheckFailed(features) {
    const feature_names = features.map((item) => item.name);
    const features_message = _joinWords(feature_names);

    let intersected_tiers = _upgradableTiers;
    features.forEach((item) => {
        intersected_tiers = _intersection(intersected_tiers, item.allowed_tiers);
    });

    const allowed_tiers_message = _joinTiers(intersected_tiers);
    const list_name = `${feature_names.join("_").toLowerCase()}_tier_checker`;

    addPopupGtagEvent(SUBSCRIPTION_URL, list_name);
    notifier.confirm(
        `${features_message} is not available in the current plan. Please upgrade to ${allowed_tiers_message} to use it.`,
        () => {
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

    const permissions = await getFeaturePermissions();
    const tier = realtimeData.orderInfo.tier;

    const signature = getSignatureFromArgs(args);
    const getArg = (key) => args[signature.indexOf(key)];

    for (let permission of permissions.generate) {
        if (permission.allowed_tiers.includes(tier)) {
            continue;
        }

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
        features.push(permission);
    }

    if (features.length != 0) {
        _tierCheckFailed(features);
    }

    _checkSamplingSteps(tabname, getArg, permissions, tier);
    _checkControlNetUnits(tabname, getArg, permissions, tier);
    await _checkSafetyAgreement(getArg, permissions, tier);
}

async function tierCheckButtonInternal(feature_name) {
    const permissions = await getFeaturePermissions();
    const permission = permissions.buttons[feature_name];

    if (permission.allowed_tiers.includes(realtimeData.orderInfo.tier)) {
        return;
    }
    _tierCheckFailed([permission]);
}

function tierCheckButton(feature_name) {
    return async (...args) => {
        await tierCheckButtonInternal(feature_name);
        return args;
    };
}

function checkQueue(is_queued, textinfo) {
    if (realtimeData.orderInfo.tier != "Free") {
        return false;
    }
    if (!is_queued) {
        return false;
    }
    let result = textinfo.match(/^In queue\((\d+) ahead\)/);
    if (!result) {
        return false;
    }

    let ahead = Number(result[1]);
    if (ahead <= 1) {
        return false;
    }
    addPopupGtagEvent(SUBSCRIPTION_URL, "free_queue");
    notifier.confirm(
        `Your task is in queue and ${ahead} tasks ahead, \
        upgrade to shorten the queue and get faster service. \
        Or join our ${_AFFILIATE_PROGRAM} to earn cash or credits \
        and use it to upgrade to <b>Basic</b> plan.`,
        () => {
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
    return true;
}

async function upgradeCheck(upgrade_info) {
    if (!upgrade_info.need_upgrade) {
        return;
    }

    let event, message, title, confirm_text, url;

    switch (upgrade_info.reason) {
        case "NSFW_CONTENT":
            event = "nsfw_checker";
            title = "Upgrade Now";
            confirm_text = "Upgrade";
            url = SUBSCRIPTION_URL;

            const _ALLOWED_TIERS = ["Basic", "Plus", "Pro", "Api"];
            const allowed_tiers_message = _joinWords(_ALLOWED_TIERS, "or");

            let hint;
            if (realtimeData.orderInfo.tier.toLowerCase() === "appsumo ltd tier 1") {
                hint = "lift these restrictions";
            } else {
                hint = "enable your private image storage";
            }

            message = `Potential NSFW content was detected in the generated image, \
                upgrade to ${allowed_tiers_message} to ${hint}. \
                Or join our ${_AFFILIATE_PROGRAM} \
                to earn cash or credits and use it to upgrade to a higher plan.`;

            break;

        case "INSUFFICIENT_CREDITS":
            event = "insufficient_credits";
            title = "Upgrade Now";
            confirm_text = "Upgrade";
            url = SUBSCRIPTION_URL;

            message = `You have ran out of your credits, please purchase more or upgrade to a \
                higher plan. Join our ${_AFFILIATE_PROGRAM} to earn cash or credits.`;

            break;

        case "INSUFFICIENT_DAILY_CREDITS":
            event = "insufficient_daily_credits";
            title = "Subscribe Now";
            confirm_text = "Subscribe Now";
            url = SUBSCRIPTION_URL;

            const orderInfo = realtimeData.orderInfo;
            const price_id = orderInfo.price_id;
            if (price_id) {
                const params = new URLSearchParams({
                    price_id: price_id,
                    client_reference_id: Base64.encodeURI(
                        JSON.stringify({ user_id: orderInfo.user_id }),
                    ),
                    allow_promotion_codes: true,
                    current_url: window.location.href,
                });
                url = `/pricing_table/checkout?${params.toString()}`;
            }

            message =
                "Your daily credits limit for the trial has been exhausted. \
                Subscribe now to unlock the daily restrictions.";

            break;

        case "REACH_CONCURRENCY_LIMIT":
            event = "reach_concurrency_limit";
            title = "Upgrade Now";
            confirm_text = "Upgrade";
            url = SUBSCRIPTION_URL;

            const permissions = await getFeaturePermissions();
            const tier = realtimeData.orderInfo.tier;

            const current_limit = permissions.limits[tier];
            if (!current_limit) {
                throw `user tier "${tier}" not found in the "limits" of permissions.`;
            }

            const max_concurrent_tasks = current_limit.max_concurrent_tasks;

            const getUnit = (limit) => (limit === 1 ? "task" : "tasks");

            message = `Your current plan allows only ${max_concurrent_tasks} concurrent \
                ${getUnit(max_concurrent_tasks)}.`;

            const higher_limits = permissions.upgradablelimits.filter(
                (item) => item.max_concurrent_tasks > max_concurrent_tasks,
            );
            if (higher_limits.length > 0) {
                message += " Upgrade to:";
                message += "<ul style='list-style: inside'>";
                for (let limit of higher_limits) {
                    message += `<li><b>${limit.tier}</b> to run up to ${limit.max_concurrent_tasks} \
                        ${getUnit(limit.max_concurrent_tasks)} simultaneously;</li>`;
                }
                message += "</ul>";
            }
            break;

        default:
            throw `Unknown upgrade reason: "${upgrade_info.reason}".`;
    }

    notifier.confirm(
        message,
        () => {
            if (url.includes("pricing_table/checkout")) {
                addUpgradeGtagEvent(url, event);
            }
            window.open(url, "_blank");
        },
        () => {},
        {
            labels: {
                confirm: title,
                confirmOk: confirm_text,
            },
        },
    );
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

async function _checkSafetyAgreement(getArg, permissions, tier) {
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
