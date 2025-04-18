const languageCookieKey = "localization";
const LANGUAGE_NAMES = {
    en_US: "English",
    de_DE: "Deutsch",
    es_ES: "Español",
    fi_FI: "Suomi",
    fr_FR: "Français",
    it_IT: "Italiano",
    ja_JP: "日本語",
    ko_KR: "한국어",
    no_NO: "Norwegian",
    pt_BR: "Português (Brasil)",
    ru_RU: "Pусский",
    tr_TR: "Türkçe",
    zh_CN: "中文(简体)",
    zh_TW: "中文(繁體)",
};

let _languageCodes = null;

function getLanguageCodes() {
    if (!_languageCodes) {
        const languageListNode = gradioApp().querySelector(`#language-list`);
        _languageCodes = JSON.parse(languageListNode.textContent.replaceAll("'", '"'));
    }
    return _languageCodes;
}

function setSelectChecked(selectId, checkValue) {
    const select = gradioApp().querySelector(`#${selectId}`);

    for (let i = 0; i < select.options.length; i++) {
        if (select.options[i].value == checkValue) {
            select.options[i].selected = true;
            break;
        }
    }
}

function generateLanguageSelectOptions() {
    const footerNode = gradioApp().querySelector(`#footer-nav`);

    const selectNode = document.createElement("select");
    selectNode.classList = "language-list";
    selectNode.title = "Select Language";
    selectNode.id = "language-select";

    getLanguageCodes().forEach((code) => {
        const optionNode = document.createElement("option");
        optionNode.value = code;
        optionNode.label = LANGUAGE_NAMES[code];

        selectNode.appendChild(optionNode);
    });
    footerNode.appendChild(selectNode);
}

function adaptMobile() {
    const footerNode = gradioApp().querySelector(`#footer-nav`);
    const navList = footerNode.querySelectorAll(".nav-item");
    const isMobile = window.innerWidth < 640;
    isMobile && navList.forEach((nav) => nav.classList.remove("nav-item"));
}

function initialLanguage() {
    if (!window.Cookies) {
        return;
    }

    const languageCodes = getLanguageCodes();
    let code = Cookies.get(languageCookieKey);
    if (!languageCodes.includes(code)) {
        code = "en_US";
    }
    setSelectChecked("language-select", code);

    gradioApp()
        .querySelector(`#language-select`)
        .addEventListener("change", (event) => {
            Cookies.set(languageCookieKey, event.target.value, {
                expires: 365,
                domain: "diffus.me",
            });
        });
}

onUiLoaded(() => {
    generateLanguageSelectOptions();
    adaptMobile();
    initialLanguage();
});
