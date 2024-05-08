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
let _featurePermissions = null;
let _samplingStepsArgName = "steps";

const _AFFILIATE_PROGRAM =
    '<a href="/affiliate/everyone" target="_blank" style="text-wrap: nowrap">Affiliate Program</a>';

async function getFeaturePermissions() {
    if (!_featurePermissions) {
        const response = await fetchGet("/config/feature_permissions");
        const body = await response.json();
        _featurePermissions = {
            generate: body.generate,
            buttons: Object.fromEntries(body.buttons.map((item) => [item.name, item])),
            limits: body.limits,
        };
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
    for (let tier of ["Basic", "Plus", "Pro", "Api"]) {
        if (tiers.includes(tier)) {
            unique_tiers.push(tier);
        }
    }
    return _joinWords(unique_tiers, "or");
}

function _getCurrentAndHigherLimits(permissions, tier) {
    const limits = permissions.limits;
    const index = limits.findIndex((item) => item.tier === tier);
    if (index === -1) {
        throw `user tier "${tier}" not found in the "limits" of permissions.`;
    }
    const current_limit = limits[index];
    const higher_limits = limits.slice(index + 1);

    return [current_limit, higher_limits];
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

function _checkSamplingSteps(getArg, permissions, tier) {
    const steps = getArg(_samplingStepsArgName);

    let [current_limit, higher_limits] = _getCurrentAndHigherLimits(permissions, tier);
    const max_sampling_steps = current_limit.max_sampling_steps;

    if (steps <= max_sampling_steps) {
        return;
    }

    let message = `Your current plan allows for a maximum of ${current_limit.max_sampling_steps} sampling steps.`;

    higher_limits = higher_limits.filter((item) => item.max_sampling_steps > max_sampling_steps);
    if (higher_limits.length > 0) {
        message += " Upgrade to:";
        message += "<ul style='list-style: inside'>";
        for (let limit of higher_limits) {
            message += `<li><b>${limit.tier}</b> to increase your limit to \
                ${limit.max_sampling_steps} sampling steps;</li>`;
        }
        message += "</ul>";
    }

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

function _tierCheckFailed(features, allowed_tiers) {
    const features_message = _joinWords(features);
    const allowed_tiers_message = _joinTiers(allowed_tiers);
    const list_name = `${features.join("_").toLowerCase()}_tier_checker`;

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
    const allowed_tiers = [];

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
        features.push(permission.name);
        allowed_tiers.push(...permission.allowed_tiers);
    }

    if (features.length != 0) {
        _tierCheckFailed(features, allowed_tiers);
    }

    _checkSamplingSteps(getArg, permissions, tier);
}

async function tierCheckButtonInternal(feature_name) {
    const permissions = await getFeaturePermissions();
    const permission = permissions.buttons[feature_name];

    if (permission.allowed_tiers.includes(realtimeData.orderInfo.tier)) {
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
            message = `Potential NSFW content was detected in the generated image, \
                upgrade to ${allowed_tiers_message} to enable your private image storage. \
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

            let [current_limit, higher_limits] = _getCurrentAndHigherLimits(permissions, tier);
            const max_concurrent_tasks = current_limit.max_concurrent_tasks;

            const getUnit = (limit) => (limit === 1 ? "task" : "tasks");

            message = `Your current plan allows only ${max_concurrent_tasks} concurrent \
                ${getUnit(max_concurrent_tasks)}.`;

            higher_limits = higher_limits.filter(
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
