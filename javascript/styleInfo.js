async function _listCandidateStyles(style_names) {
    const params = new URLSearchParams();
    for (let style_name of style_names) {
        params.append("style", style_name);
    }
    const url = `/internal/candidate_styles?${params.toString()}`;
    try {
        const response = await fetchGet(url);
        if (!response.ok) {
            console.error(
                `Request candidate styles failed, url: "${url}", reason: "${response.status} ${response.statusText}"`,
            );
            throw _REQUEST_FAILED;
        }
        const content = await response.json();
        return content.styles;
    } catch (error) {
        console.error(`Request candidate styles failed due to exception, url: "${url}"`);
        console.error(error);
        throw _REQUEST_FAILED;
    }
}

function _getAllStyleInfo(style_names, candidate_styles) {
    const style_tree = {};
    for (let item of candidate_styles) {
        style_tree[item.name] = item;
    }

    const all_style_info = [];
    for (let name of style_names) {
        const style_info = style_tree[name];
        if (!style_info) {
            _alert(`style "${name}" not found`);
        }
        all_style_info.push(style_info);
    }
    return all_style_info;
}

async function getAllStyleInfo(args) {
    const signature = getSignatureFromArgs(args);
    const index = signature.indexOf("all_style_info");
    if (index === -1) {
        _alert('"all_style_info" not found in signature');
    }

    const style_names = args[signature.indexOf("prompt_styles")];
    if (style_names.length == 0) {
        return [index, []];
    }

    try {
        const candidate_styles = await _listCandidateStyles(style_names);
        const all_style_info = _getAllStyleInfo(style_names, candidate_styles);
        return [index, all_style_info];
    } catch (error) {
        if (error === _REQUEST_FAILED) {
            console.error('Set "all_style_info" to null due to request fail');
            return [index, null];
        }
        throw error;
    }
}
