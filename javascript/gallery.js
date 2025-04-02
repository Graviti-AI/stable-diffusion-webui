function initMobileCanvas(canvas) {
    if (!("ontouchstart" in window)) {
        return;
    }

    const uuid = canvas.uuid;

    const container = document.getElementById(`imageContainer_${uuid}`);
    const uploadButton = document.getElementById(`uploadButton_${uuid}`);
    const toolbar = document.getElementById(`toolbar_${uuid}`);

    container.addEventListener("click", (_) => {
        if (!canvas.img) {
            uploadButton.click();
        }
    });
    toolbar.addEventListener("click", (event) => {
        event.stopPropagation();
    });
}

function getDiffusApp() {
    if ((!"diffusApp") in window.parent) {
        throw "diffusApp not found in the parent window.";
    }

    return window.parent.diffusApp;
}

function setDiffusCheckpoint(title) {
    const diffusApp = getDiffusApp();
    diffusApp.checkpoints.setTitle(title);
}

function updateFavoriteCheckpoints() {
    const checkpoints = getDiffusApp().checkpoints.listInfo();

    return { value: checkpoints, __type__: "update" };
}

async function refreshFavoriteCheckpoints() {
    const checkpointsApp = getDiffusApp().checkpoints;
    await checkpointsApp.refesh();
    const checkpoints = checkpointsApp.listInfo();

    return { value: checkpoints, __type__: "update" };
}

function updateFavoriteCheckpointsDowndownWrapper(default_value) {
    function inner(value, checkpoints) {
        const choices = checkpoints.map((item) => {
            const name = `${item.filename} [${item.sha256.slice(0, 10)}]`;
            return [name, name];
        });

        const result = {
            choices: choices,
            __type__: "update",
        };

        if (default_value) {
            result.choices.unshift([default_value, default_value]);
        }
        if (!value) {
            result.value = result.choices[0][0];
        }
        return result;
    }
    return inner;
}

function _XYZGridHelper(index, flag) {
    function inner(...args) {
        args[index] = flag(args)
            ? args[index].map((item) => `${item.filename} [${item.sha256.slice(0, 10)}]`)
            : null;
        return args;
    }
    return inner;
}

const XYZGridHelpers = {
    select_axis: _XYZGridHelper(4, (args) =>
        ["Checkpoint name", "Refiner checkpoint"].includes(args[0]),
    ),
    fill: _XYZGridHelper(2, (args) => ["Checkpoint name", "Refiner checkpoint"].includes(args[0])),
    change_choice_mode: _XYZGridHelper(10, (args) =>
        [args[1], args[4], args[7]].some((type) =>
            ["Checkpoint name", "Refiner checkpoint"].includes(type),
        ),
    ),
};
