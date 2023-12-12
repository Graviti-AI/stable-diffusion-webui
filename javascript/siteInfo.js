/*
 * @Date: 2023-11-19 10:16:55
 * @LastEditors: yuanbo.chen yuanbo.chen@graviti.com
 * @LastEditTime: 2023-12-12 23:15:21
 * @FilePath: /stable-diffusion-webui/javascript/siteInfo.js
 */
class ChannelInfo {
  async getChannelInfo() {
    try {
      const res = await fetchGet('api/user_channel');
      const channelInfo = await res.json();
      if (channelInfo) {
        document.title = channelInfo.title || '';
        channelResult = channelInfo;
        this.changeDiscordIcon(channelInfo);
        this.hideCheckinBtn(channelInfo);
        this.changeFreeCreditLink(channelInfo);
      }
      this.iniatlLanguage();
    } catch (e) {
      console.log(e);
    }
  }

  async changeFreeCreditLink(channelInfo) {
    const signNode = gradioApp().querySelector('.user-content #sign');
    const linkNode = signNode.querySelector('a');
    if (!hasSingPermission) {
      if (channelInfo) {
        const {
          prices: { credit_package },
        } = channelInfo;
        if (orderInfoResult) {
          const resultInfo = { user_id: orderInfoResult.user_id };
          const referenceId = Base64.encodeURI(JSON.stringify(resultInfo));
          linkNode.href = `${credit_package.price_link}?prefilled_email=${orderInfoResult.email}&client_reference_id=${referenceId}`;
        } else {
          linkNode.href = credit_package.price_link;
        }
      }
    }
    changeCreditsPackageLink();
  }

  hideCheckinBtn(channelInfo) {
    const signBtn = gradioApp().querySelector('#sign');
    const { name } = channelInfo;
    // hide sign button if channel is not graviti.
    if (hasSingPermission && signBtn && name !== 'graviti.com') {
      signBtn.style.display = 'none';
    }
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

  iniatlLanguage() {
    if (!window.Cookies) return;

    const navigatorLanguage = navigator.language.replaceAll('-', '_');
    const cookieLanguage = Cookies.get(languageCookieKey);
    const languageListNode = gradioApp().querySelector(`#language-list`);

    const laguageList = JSON.parse(
      languageListNode.textContent.replaceAll("'", '"')
    );

    if (cookieLanguage) {
      setSelectChecked('language-select', cookieLanguage);
    } else {
      const language = laguageList.find(
        (item) => item.toLowerCase() === navigatorLanguage.toLowerCase()
      );
      // set default language from channel
      if (channelResult) {
        const { language: channelLanguage } = channelResult;
        setSelectChecked('language-select', channelLanguage);
        Cookies.set(languageCookieKey, channelLanguage);
      } else {
        setSelectChecked('language-select', language ? language : 'None');
        Cookies.set(languageCookieKey, navigatorLanguage);
      }
      location.reload();
    }
    gradioApp()
      .querySelector(`#language-select`)
      .addEventListener('change', (event) => {
        Cookies.set(languageCookieKey, event.target.value);
        location.reload();
      });
  }
}

// get site info
onUiLoaded(function () {
  new ChannelInfo().getChannelInfo();
});
