class SignForCredits {
  async sign() {
    const signNode = gradioApp().querySelector('.user-content #sign');
    try {
      const response = await fetch(`/api/user_sign`, {
        method: 'POST',
        credentials: 'include',
      });
      const { gained_inference_count, continue_signed_days } =
        await response.json();
      if (continue_signed_days === 1) {
        notifier.success(
          'Get extra 5 credits tomorrow,<a href="/user#/billing">See Details</a>'
        );
      } else if (continue_signed_days >= 2 && continue_signed_days <= 6) {
        notifier.success(
          `Extra ${gained_inference_count} Credits today. Get extra 5 credits tomorrow<p><a href="/user#/billing">See Details</a></p>`
        );
      } else {
        notifier.success(
          `Congratulations! Extra ${gained_inference_count} Credits today! Earn extra 30 credits daily<p><a href="/user#/billing">See Details</a></p>`
        );
      }
      reportEarnCreditsEvent("daily_check_in", 20 + gained_inference_count);
      signNode.style.display = 'none';
      const userContent = gradioApp().querySelector(".user-content");
      const upgradeContent = userContent.querySelector("#upgrade");
      if (upgradeContent) {
          upgradeContent.style.display = "flex";
      }
    } catch (e) {
      notifier.alert('check in error');
    }
  }
  async showActivityButtonForUser() {
    const signNode = gradioApp().querySelector('.user-content #sign');
    const linkNode = signNode.querySelector('a');
    const imgNode = signNode.querySelector('img');
    const spanNode = signNode.querySelector('span');
    const upgradeBtnNode = gradioApp().querySelector('#upgrade span');
    try {
      if (!isPcScreen) {
        upgradeBtnNode.textContent = '';
      }
      const response = await fetch(`/api/user_sign`, {
        method: 'GET',
        credentials: 'include',
      });
      const { has_sign_permission, has_signed_today } = await response.json();
      hasSingPermission = has_sign_permission;
      if (!has_sign_permission) {
        //signNode.title = 'Unlock more features with your Stable Diffusion generator';
        //imgNode.src = '/public/image/unlock.png';
        //spanNode.textContent = isPcScreen ? 'Upgrade' : '';
        signNode.style.display = 'none';
        //if (channelResult) {
        //  changeFreeCreditLink()
        //}
      } else {
        // set after reload
        // if (Cookies && Cookies.get(languageCookieKey)) {
        //     if (localStorage.getItem('show-data-survey-info') !== 'true') {
        //         notifier.info('Help us improve our product and get a 20% discount coupon. <a href="/user#/billing"> Start Survey</a>',  {durations: {info: 0}});
        //         localStorage.setItem('show-data-survey-info', 'true');
        //     }
        // }
        if (!has_signed_today) {
          // show check-in button for diffus.me
          if (channelResult) {
            const { name } = channelResult;
            // if (name !== 'diffus.me') return;
          }
          signNode.title = 'Unlock up to 900 free credits per month';
          imgNode.src = '/public/image/calendar.png';
          spanNode.textContent = isPcScreen ? 'Check-in' : '';
          signNode.style.display = 'flex';
          linkNode.addEventListener('click', this.sign);
        } else {
          const userContent = gradioApp().querySelector(".user-content");
          const upgradeContent = userContent.querySelector("#upgrade");
          if (upgradeContent) {
              upgradeContent.style.display = "flex";
          }
        }
      }
    } catch (e) {
      console.log(e);
    }
  }
}

onUiLoaded(function () {
  new SignForCredits().showActivityButtonForUser();
});
