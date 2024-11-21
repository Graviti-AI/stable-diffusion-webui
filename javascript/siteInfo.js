/*
 * @Date: 2023-11-19 10:16:55
 * @LastEditors: yuanbo.chen yuanbo.chen@graviti.com
 * @LastEditTime: 2023-12-13 20:43:24
 * @FilePath: /stable-diffusion-webui/javascript/siteInfo.js
 */
class ChannelInfo {
  async getChannelInfo() {
    try {
      const res = await fetchGet('api/user_channel');
      const channelInfo = await res.json();
      if (channelInfo) {
        document.title = channelInfo.title || 'Diffus - Stable Diffusion Made Easy';
        channelResult = channelInfo;
        this.changeDiscordIcon(channelInfo);
        this.hideCheckinBtn(channelInfo);
        changeCreditsPackageLink();
      }
      this.initialLanguage();
    } catch (e) {
      console.log(e);
    }
  }

  hideCheckinBtn(channelInfo) {
    const signBtn = gradioApp().querySelector('#sign');
    const { name } = channelInfo;
    // hide sign button if channel is not graviti.
    //if (hasSingPermission && signBtn && name !== 'diffus.me') {
    //  signBtn.style.display = 'none';
    //}
  }

  changeDiscordIcon(channelInfo) {
    const discordIcon = gradioApp().querySelector('#discord');
    const aLink = discordIcon.querySelector('a');
    const {
      customer_support: { type, attributes, icon },
    } = channelInfo;
    if (type === 'image') {
      const hoverImge = document.createDocumentFragment();
      const hoverImgeNode = document.createElement('div');
      hoverImgeNode.className = 'hover-image';
      hoverImgeNode.style.opacity = 0;
      hoverImgeNode.innerHTML = `
            <img src="${attributes.url}" alt="" />
        `;
      hoverImge.appendChild(hoverImgeNode);
      discordIcon.appendChild(hoverImge);
      aLink.title = 'Scan Code';
      aLink.querySelector('img').src = icon;
      aLink.removeAttribute('href');
    } else {
      aLink.href = attributes.url;
      aLink.title = 'Join Discord';
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
