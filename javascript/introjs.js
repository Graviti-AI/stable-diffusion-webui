function txt2imgIntroJS() {
    return introJs().setOptions({
        showProgress: true,
        showBullets: false,
        steps: [
            {
                title: "txt2img Quick Guide",
                element: gradioApp().getElementById("sd_model_checkpoint_dropdown"),
                intro: "Select your Stable-Diffusion Checkpoint here.",
            },
            {
                element: gradioApp().getElementById("txt2img_prompt"),
                intro: "Input your prompt here. Here is an example: <p><i>polaroid photo, night photo, photo of 24 y.o beautiful woman, pale skin, bokeh, motion blur</i></p>",
            },
            {
                element: gradioApp().getElementById("txt2img_generate"),
                intro: "Click here to generate image.",
            },
            {
                element: gradioApp().getElementById("txt2img_gallery"),
                intro: "Generated image appears here.",
            },
            {
                element: gradioApp().getElementById("introjs_button"),
                title: "Enjoy the Webui",
                intro: "Click here to view guide again. <p> Join our <a href='https://discord.gg/e4UVBNuHyB'>Discord</a> for futher support.</p><br><p>Enjoy!</p>",
            },
        ],
    });
}

function img2imgIntroJS() {
    return introJs().setOptions({
        showProgress: true,
        showBullets: false,
        steps: [
            {
                title: "img2img Quick Guide",
                element: gradioApp().getElementById("sd_model_checkpoint_dropdown"),
                intro: "Select your Stable-Diffusion Checkpoint here.",
            },
            {
                element: gradioApp().getElementById("img2img_prompt"),
                intro: "Input your prompt here. Here is an example: <p><i>magnificent, celestial, ethereal, painterly, epic, majestic, magical, fantasy art, cover art, dreamy</i></p>",
            },
            {
                element: gradioApp().getElementById("img2img_image"),
                intro: "Upload your image here.",
            },
            {
                element: gradioApp().getElementById("img2img_generate"),
                intro: "Click here to generate image.",
            },
            {
                element: gradioApp().getElementById("img2img_gallery"),
                intro: "Generated image appears here.",
            },
            {
                element: gradioApp().getElementById("introjs_button"),
                title: "Enjoy the Webui",
                intro: "Click here to view guide again. <p> Join our <a href='https://discord.gg/e4UVBNuHyB'>Discord</a> for futher support.</p><br><p>Enjoy!</p>",
            },
        ],
    });
}

const _registered_tabs = {};

function registerTabIntroJS(tab_id, introjs) {
    const tab = gradioApp().getElementById(tab_id);
    const introjs_button = gradioApp().getElementById("introjs_button");
    const cookie_key = `_${tab_id}_introjs_showed`;

    introjs.onexit(() => window.Cookies.set(cookie_key, true, { expires: 360 }));

    _registered_tabs[tab_id] = { tab: tab, cookie_key: cookie_key, introjs: introjs };

    const observer = new MutationObserver((mutations) => {
        const mutation = mutations[0];
        if (mutation.attributeName !== "style") {
            return;
        }
        if (tab.style.display === "none") {
            if (
                Object.values(_registered_tabs).every((value) => value.tab.style.display === "none")
            ) {
                introjs_button.disabled = true;
                introjs_button.style.color = "#404040";
            }
            return;
        }
        introjs_button.disabled = false;
        introjs_button.style.color = null;

        if (!window.Cookies.get(cookie_key)) {
            introjs.start();
        }
    });

    observer.observe(tab, { attributes: true, attributeFilter: ["style"] });
}

function startIntroJS() {
    for (let value of Object.values(_registered_tabs)) {
        if (value.tab.style.display === "block") {
            value.introjs.start();
            return;
        }
    }
}

async function loadIntroJS() {
    registerTabIntroJS("tab_txt2img", txt2imgIntroJS());
    registerTabIntroJS("tab_img2img", img2imgIntroJS());

    const introjs_button = gradioApp().getElementById("introjs_button");
    introjs_button.addEventListener("click", startIntroJS);

    const tab = _registered_tabs["tab_txt2img"];

    if (!window.Cookies.get(tab.cookie_key)) {
        tab.introjs.start();
    }
}

onNotificationComplete(loadIntroJS);
