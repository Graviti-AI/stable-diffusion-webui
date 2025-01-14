
function onCalcResolutionHires(enable, width, height, hr_scale, hr_resize_x, hr_resize_y) {
    function setInactive(elem, inactive) {
        elem.classList.toggle('inactive', !!inactive);
    }

    var hrUpscaleBy = gradioApp().getElementById('txt2img_hr_scale');
    var hrResizeX = gradioApp().getElementById('txt2img_hr_resize_x');
    var hrResizeY = gradioApp().getElementById('txt2img_hr_resize_y');

    gradioApp().getElementById('txt2img_hires_fix_row2').style.display = opts.use_old_hires_fix_width_height ? "none" : "";

    setInactive(hrUpscaleBy, opts.use_old_hires_fix_width_height || hr_resize_x > 0 || hr_resize_y > 0);
    setInactive(hrResizeX, opts.use_old_hires_fix_width_height || hr_resize_x == 0);
    setInactive(hrResizeY, opts.use_old_hires_fix_width_height || hr_resize_y == 0);

    return [enable, width, height, hr_scale, hr_resize_x, hr_resize_y];
}

function toggleUseDifferentHRCFGScale(enabled, ditilled_cfg_scale, cfg_scale) {
    if (enabled) {
        return [
            { interactive: enabled, __type__: "update" },
            { interactive: enabled, __type__: "update" },
        ];
    }

    return [
        { interactive: enabled, value: ditilled_cfg_scale, __type__: "update" },
        { interactive: enabled, value: cfg_scale, __type__: "update" },
    ];
}

function syncHRCFGScale(enabled, value) {
    if (enabled) {
        return { __type__: "update" };
    }

    return { value: value, __type__: "update" };
}
