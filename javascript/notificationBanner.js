function showNotificationBanner() {
  const bannerHtml = `
    <div id="banner" style="display: none">
      <p id="banner-text"></p>
      <div class="announcement-bar-close" id="close-banner">
        <span
          id="close-banner-icon"
          tabindex="0"
          role="button"
          aria-label="Close Announcement"
          >×</span
        >
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML('afterbegin', bannerHtml);
  fetch("/image_server/notifications/banner", {
    method: "GET",
    credentials: "include",
  })
    .then((response) => {
      if (response.status === 200) {
        return response.json();
      }
      return Promise.reject(response);
    })
    .then((data) => {
      const notificationId = data.notification_id;
      const closedBannerNotificationId = Cookies.get(
        "_closed_banner_notification_id",
      );
      if (notificationId == closedBannerNotificationId) {
        return;
      }
      let banner = document.getElementById("banner");
      let content = gradioApp().querySelector(".gradio-container.app");
      document.getElementById("banner-text").innerHTML = data.message;
      banner.style.display = "block";
      content.style.marginTop = banner.offsetHeight + "px";
      document.getElementById("close-banner").onclick = function () {
        var banner = document.getElementById("banner");
        banner.classList.add("hide");
        setTimeout(function () {
          banner.style.display = "none";
          content.style.marginTop = "0px";
          Cookies.set("_closed_banner_notification_id", notificationId, {
            expires: 90,
          });
        }, 500); // Must match the transition duration
      };
    })
    .catch((error) => {
      console.error("Failed to fetch notification banner", error);
    });
}

onUiLoaded(function () {
  showNotificationBanner();
});
