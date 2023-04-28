const localization_name_mapper = {
    'None': 'English',
    'de_DE': 'Deutsch',
    'es_ES': 'Español',
    'fi_FI': 'Suomi',
    'it_IT': 'Italiano',
    'ja_JP': '日本語',
    'ko_KR': '한국어',
    'no_NO': 'Norwegian',
    'pt_BR': 'Português (Brasil)',
    'ru_RU': 'Pусский',
    'tr_TR': 'Türkçe',
    'zh_CN': '中文(简体)',
    'zh_TW': '中文(繁體)',
}

const languageCookieKey = 'localization';

function setSelectChecked(selectId, checkValue){  
    var select = gradioApp().querySelector(`#${selectId}`);  
 
    for (var i = 0; i < select.options.length; i++){  
        if (select.options[i].value == checkValue){  
            select.options[i].selected = true;  
            break;  
        }  
    }  
}

function generateLanguageSelectOptions() {
    const footerNode = gradioApp().querySelector(`#footer-nav`);
    const languageListNode = gradioApp().querySelector(`#language-list`);

    const selectNode = document.createElement('select');
    selectNode.classList = 'language-list';
    selectNode.title = 'Select Language';
    selectNode.id = 'language-select';

    const laguageList = JSON.parse(languageListNode.textContent.replaceAll('\'', '"'));
    laguageList.forEach(language => {
        const optionNode =  document.createElement('option');
        optionNode.value = language;
        optionNode.label = localization_name_mapper[language];

        selectNode.appendChild(optionNode);
    })
    footerNode.appendChild(selectNode);

}

function iniatlLanguage() {
    const navigatorLanguage = navigator.language;
    const cookieLanguage = Cookies.get(languageCookieKey);
    const languageListNode = gradioApp().querySelector(`#language-list`);

    const laguageList = JSON.parse(languageListNode.textContent.replaceAll('\'', '"'));

    if (cookieLanguage) {
        setSelectChecked('language-select', cookieLanguage);
    } else {
        setSelectChecked('language-select', laguageList.includes(navigatorLanguage) ? navigatorLanguage : 'None');
        Cookies.set(languageCookieKey, navigatorLanguage);
    }
    gradioApp().querySelector(`#language-select`).addEventListener('change', (event) => {
        Cookies.set(languageCookieKey, event.target.value);
        location.reload();
    })
}

onUiLoaded(() => {
    generateLanguageSelectOptions()
    iniatlLanguage()
})


