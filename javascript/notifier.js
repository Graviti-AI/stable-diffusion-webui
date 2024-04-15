let notifierGlobalOptions = {
  position: "bottom-right",
  icons: { enabled: false },
  minDurations: {
    async: 30,
    "async-block": 30,
  },
};

var notifier = new AWN(notifierGlobalOptions);

function getLatestNotification(interval = 10, timeoutId = null) {
  fetch(`/image_server/notifications/latest?interval=${interval}`, {
    method: "GET",
    credentials: "include",
    cache: "no-cache",
  })
    .then((response) => {
      if (response.status === 200) {
        return response.json();
      }
      return Promise.reject(response);
    })
    .then(async (newNotification) => {
      if (
        newNotification.notification_id >= 0 &&
        (newNotification.message || newNotification.title)
      ) {
        const resultInfo = { user_id: newNotification.user_id };
        const referenceId = Base64.encodeURI(JSON.stringify(resultInfo));
        const updatedMessage = updateStripeOrPricingUrls(
          newNotification.message,
          { client_reference_id: referenceId },
        );
        const updatedTitle = updateStripeOrPricingUrls(
          newNotification.title,
          { client_reference_id: referenceId },
        );
        if (newNotification.notification_type === "error") {
          notifier.alert(
            `<div class="notification-sub-main">${updatedMessage}</div>`,
            {
              labels: { alert: updatedTitle },
              durations: { alert: newNotification.duration * 1000 },
            },
          );
        } else if (newNotification.notification_type === "warning") {
          notifier.warning(
            `<div class="notification-sub-main">${updatedMessage}</div>`,
            {
              labels: { warning: updatedTitle },
              durations: { warning: newNotification.duration * 1000 },
            },
          );
        } else if (newNotification.notification_type === "success") {
          notifier.success(
            `<div class="notification-sub-main">${updatedMessage}</div>`,
            {
              labels: { success: updatedTitle },
              durations: { success: newNotification.duration * 1000 },
            },
          );
        } else {
          notifier.info(
            `<div class="notification-sub-main">${updatedMessage}</div>`,
            {
              labels: { info: updatedTitle },
              durations: { info: newNotification.duration * 1000 },
            },
          );
        }
      }
    })
    .catch((error) => {
      console.error(error);
    });
}

async function pullNewNotification() {
  const interval = 60;
  const timeoutId = setTimeout(pullNewNotification, interval * 1000);
  getLatestNotification(interval, timeoutId);
}

onUiLoaded(function () {
  pullNewNotification();
});
