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
                element: gradioApp().getElementById("txt2img_introjs_button"),
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
                element: gradioApp().getElementById("img2img_introjs_button"),
                title: "Enjoy the Webui",
                intro: "Click here to view guide again. <p> Join our <a href='https://discord.gg/e4UVBNuHyB'>Discord</a> for futher support.</p><br><p>Enjoy!</p>",
            },
        ],
    });
}

function registerIntroJS(tabname, introjs) {
    const tab_id = `tab_${tabname}`;
    const button_id = `${tabname}_introjs_button`;

    const tab = gradioApp().getElementById(tab_id);
    const introjs_button = gradioApp().getElementById(button_id);

    const cookie_key = `_${tab_id}_introjs_showed`;

    introjs.onexit(() => window.Cookies.set(cookie_key, true, { expires: 360 }));

    introjs_button.addEventListener("click", () => introjs.start());

    const observer = new MutationObserver((mutations) => {
        const mutation = mutations[0];
        if (mutation.attributeName !== "style" || tab.style.display === "none") {
            return;
        }

        if (!window.Cookies.get(cookie_key)) {
            introjs.start();
        }
    });

    observer.observe(tab, { attributes: true, attributeFilter: ["style"] });

    return { introjs, cookie_key };
}

function loadIntroJS() {
    const { introjs, cookie_key } = registerIntroJS("txt2img", txt2imgIntroJS());
    registerIntroJS("img2img", img2imgIntroJS());

    if (!window.Cookies.get(cookie_key)) {
        introjs.start();
    }
}

onUiLoaded(loadIntroJS);
