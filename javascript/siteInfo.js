let channelResult = null;

class ChannelInfo {
  async getChannelInfo() {
    try {
      const res = await fetchGet('/api/user_channel');
      const channelInfo = await res.json();
      if (channelInfo) {
        document.title = channelInfo.title || 'Diffus - Stable Diffusion Made Easy';
        channelResult = channelInfo;
      }
      this.initialLanguage();
    } catch (e) {
      console.log(e);
    }
  }

  chooseLanguage(availableLanguages, userLanguage) {
    // Normalize the language code to xx_XX format
    userLanguage = userLanguage.replace('-', '_');

    // Check for a direct match
    if (availableLanguages.includes(userLanguage)) {
      return userLanguage;
    }

    // Check for a match with only the language part
    const languagePart = userLanguage.split('_')[0];
    const matchedLanguage = availableLanguages.find(lang => lang.startsWith(languagePart));
    if (matchedLanguage) {
      return matchedLanguage;
    }

    // Fallback to default language
    return 'None';
  }

  initialLanguage() {
    if (!window.Cookies) return;

    const cookieLanguage = Cookies.get(languageCookieKey);
    const languageListNode = gradioApp().querySelector(`#language-list`);
    const languageList = JSON.parse(
      languageListNode.textContent.replaceAll("'", '"')
    );

    let selectedLanguage = 'None';
    // language priority:
    // 1. user setting in cookie
    // 2. channel setting
    // 3. browser language
    if (cookieLanguage) {
      selectedLanguage = cookieLanguage;
    } else {
      if (channelResult && channelResult.language) {
        selectedLanguage = channelResult.language;
      } else {
        selectedLanguage = navigator.language || navigator.userLanguage;
      }
    }

    selectedLanguage = this.chooseLanguage(languageList, selectedLanguage)

    // always update cookie, to keep it not expired
    const cookieMeta = { expires: 365, domain: 'diffus.me' };
    Cookies.set(languageCookieKey, selectedLanguage, cookieMeta);

    // update language-select list to show current selected language
    setSelectChecked('language-select', selectedLanguage);
    if (!cookieLanguage && language != 'None') {
      location.reload();
    }

    gradioApp()
      .querySelector(`#language-select`)
      .addEventListener('change', (event) => {
        Cookies.set(languageCookieKey, event.target.value, cookieMeta);
        location.reload();
      });
  }
}

// get site info
onUiLoaded(function () {
  new ChannelInfo().getChannelInfo();
});
