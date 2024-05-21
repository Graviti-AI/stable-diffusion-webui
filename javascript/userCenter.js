let openingAnotherModal = false;

function observeModalClose(modalElement, onClosedCallback) {
  let observer = new MutationObserver(function(mutations) {
    // check for removed target
    mutations.forEach(function(mutation) {
      let nodes = Array.from(mutation.removedNodes);
      let directMatch = nodes.indexOf(modalElement) > -1
      let parentMatch = nodes.some(parent => parent.contains(modalElement));
      if (directMatch) {
        if (typeof onClosedCallback === 'function') {
          onClosedCallback(modalElement);
        }
        observer.disconnect();
      } else if (parentMatch) {
        if (typeof onClosedCallback === 'function') {
          onClosedCallback(modalElement);
        }
        observer.disconnect();
      }
    });
  });

  let config = {
    subtree: true,
    childList: true
  };
  observer.observe(document.body, config);
}

function preloadImage(url, onloadCallback, onerrorCallback) {
  let img = new Image();
  img.src = url;
  img.onload = onloadCallback;
  img.onerror = onerrorCallback;
}

const loadImages = (htmlResponse) => new Promise((resolve, reject) => {
  let doc = document.implementation.createHTMLDocument();
  doc.body.innerHTML = htmlResponse;
  const imgs = doc.body.querySelectorAll("img");
  const totalNumImages = imgs.length;
  let imageCount = 0;

  const imageLoadCallback = () => {
    imageCount += 1;
    if (imageCount == totalNumImages) {
      resolve(doc);
    }
  }
  const onerrorCallback = (error) => {reject(error);}
  imgs.forEach(elem => {
    preloadImage(elem.src, imageLoadCallback, onerrorCallback);
  });
});

function getCurrentUserName() {
  const orderInfo = realtimeData.orderInfo;
  return orderInfo.name;
}

function getCurrentUserAvatar() {
  const userAvatarUrl = gradioApp().querySelector("#user_info img").src;
  return userAvatarUrl;
}

function showNotification(userName, avatarUrl, closeCallback=null) {
  fetch(
    '/webui/notification?' + new URLSearchParams({
        avatar_url: avatarUrl,
        user_name: userName,
    }),
    {
      method: 'GET',
      credentials: 'include',
    }
  )
  .then(response => {
    if (response.status === 200) {
      return response.json();
    }
    return Promise.reject(response);
  })
  .then((data) => {
    if (data && data.show) {
      let doc = document.implementation.createHTMLDocument();
      doc.body.innerHTML = data.html;
      let arrayScripts = [].map.call(doc.getElementsByTagName('script'), function(el) {
        return el;
      });
      for (const index in arrayScripts) {
        doc.body.removeChild(arrayScripts[index]);
      }
      const modal = notifier.modal(doc.body.innerHTML);
      for (const index in arrayScripts) {
        let new_script = document.createElement("script");
        if (arrayScripts[index].src) {
            new_script.src = arrayScripts[index].src;
        } else {
            new_script.innerHTML = arrayScripts[index].innerHTML;
        }
        document.body.appendChild(new_script);
      }
      if (typeof closeCallback === 'function') {
        observeModalClose(modal.newNode, closeCallback);
      }
    } else {
      if (typeof closeCallback === 'function') {
        closeCallback();
      }
    }
  })
  .catch((error) => {
      console.error('Notification error:', error);
      if (typeof closeCallback === 'function') {
        closeCallback();
      }
  });
}

let _notificationShowed = false;
function callShowNotification() {
  if (!_notificationShowed) {
    _notificationShowed = true;
    const userName = getCurrentUserName();
    const userAvatarUrl = getCurrentUserAvatar();

    showNotification(userName, userAvatarUrl, executeNotificationCallbacks);
  }
}

function renderInPopup(doc, onClosedCallback=null) {
  let arrayScripts = [].map.call(doc.getElementsByTagName('script'), function(el) {
    return el;
  });
  for (const index in arrayScripts) {
    doc.body.removeChild(arrayScripts[index]);
  }
  const modal =notifier.modal(doc.body.innerHTML);
  for (const index in arrayScripts) {
    let new_script = document.createElement("script");
    if (arrayScripts[index].src) {
      new_script.src = arrayScripts[index].src;
    } else {
      new_script.innerHTML = arrayScripts[index].innerHTML;
    }
    document.body.appendChild(new_script);
  }
  window.openingAnotherModal = false;
  if (typeof onClosedCallback === 'function') {
    observeModalClose(modal.newNode, onClosedCallback);
  }
}

function showInspirationPopup() {
  if (typeof posthog === 'object') {
    posthog.capture('Inspiration button clicked.');
  }
  let loadPromise =new Promise((resolve, reject) => {
    fetch('/inspire/html', {
      method: 'POST',
      headers: {
          'Content-Type': 'application/json'
      },
      body: JSON.stringify({
      })
    })
    .then(response => {
      if (response.status === 200) {
        return response.text();
      }
      return Promise.reject(response);
    })
    .then(htmlResponse => {
      loadImages(htmlResponse)
      .then((doc) => {resolve(doc)})
      .catch((error) => {reject(error)});
    })
    .catch((error) => {reject(error)});
  });
  notifier.async(
    loadPromise,
    (doc) => {renderInPopup(doc);},
    (error) => {console.error('Error:', error);},
    "Selecting a good piece for you!"
  );
}

function popupHtmlResponse(htmlResponse, onClosedCallback=null) {
  loadImages(htmlResponse)
  .then((doc) => {
    renderInPopup(doc, onClosedCallback);
  })
  .catch((error) => {
    console.error("Error:", error);
    window.openingAnotherModal = false;
    if (typeof onClosedCallback === 'function') {
      onClosedCallback();
    }
  });
}

function notifyUserTheShareCampaign(userName, avatarUrl) {
  const showed = window.Cookies.get("_1000by1000showed");
  if (!showed) {
    if (!userName) {
      userName = getCurrentUserName();
    }
    if (!avatarUrl) {
      avatarUrl = getCurrentUserAvatar();
    }
    fetch('/share/group/create/html', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ avatar_url: avatarUrl, user_name: userName })
    })
    .then(response => {
      if (response.status === 200) {
        return response.text();
      }
      return Promise.reject(response);
    })
    .then((data) => {
      let doc = document.implementation.createHTMLDocument();
      doc.body.innerHTML = data;
      let arrayScripts = [].map.call(doc.getElementsByTagName('script'), function(el) {
        return el;
      });
      for (const index in arrayScripts) {
        doc.body.removeChild(arrayScripts[index]);
      }
      const shareButton = doc.body.querySelector("button.share-group-share-btn");
      const checkStatusButton = doc.body.querySelector("button.share-group-status-btn");
      if (shareButton || checkStatusButton) {
        const modal =notifier.modal(doc.body.innerHTML);
        for (const index in arrayScripts) {
          let new_script = document.createElement("script");
          if (arrayScripts[index].src) {
            new_script.src = arrayScripts[index].src;
          } else {
            new_script.innerHTML = arrayScripts[index].innerHTML;
          }
          document.body.appendChild(new_script);
        }
        window.Cookies.set("_1000by1000showed", true, { expires: 28 });
        observeModalClose(modal.newNode, (modalElement) => {
          const elementWithSameId = document.getElementById(modalElement.id);
          if (!window.openingAnotherModal && !elementWithSameId) {
            callShowNotification();
          }
        });
      } else {
        callShowNotification();}
    })
    .catch((error) => {
      console.error('Error:', error);
      callShowNotification();
    });
  } else {
    callShowNotification();
  }
}

async function joinShareGroupWithId(share_id, userName=null, userAvatarUrl=null) {
  if (!userName) {
    userName = getCurrentUserName();
  }
  if (!userAvatarUrl) {
    userAvatarUrl = getCurrentUserAvatar();
  }
  if (share_id) {
    fetch('/share/group/join', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        group_info: {
          share_id: share_id
        },
        avatar: {
          avatar_url: userAvatarUrl,
          user_name: userName
        }
      })
    })
    .then(response => {
      if (response.status === 200) {
        return response.json();
      }
      return Promise.reject(response);
    })
    .then((data) => {
      if (data.event_code != 202) {
        fetch('/share/group/join/html', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            user_name: userName,
            user_avatar_url: userAvatarUrl,
            event_code: data.event_code,
            share_group: data.share_group
          })
        })
        .then(response => {
          if (response.status === 200) {
            return response.text();
          }
          return Promise.reject(response);
        })
        .then((htmlResponse) => {popupHtmlResponse(htmlResponse, (modalElement) => {
          const elementWithSameId = document.getElementById(modalElement.id);
          if (!window.openingAnotherModal && !elementWithSameId) {callShowNotification();}
        });})
        .catch((error) => {
          console.error('Error:', error);
          window.openingAnotherModal = false;
          callShowNotification();
        });
      } else {
        window.openingAnotherModal = false;
        callShowNotification();
      }
    })
    .catch((error) => {
      console.error('Error:', error);
      window.openingAnotherModal = false;
      callShowNotification();
    });
  } else {
    callShowNotification();
  }
}

async function joinShareGroup(userName=null, avatarUrl=null) {
  const urlParams = new URLSearchParams(window.location.search);
  const share_id = urlParams.get('share_id');

  if (share_id) {
    joinShareGroupWithId(share_id, userName, avatarUrl);
  } else {
    notifyUserTheShareCampaign(userName, avatarUrl);
  }
}

function renderHtmlResponse(elem, url, method, onSucceeded=null, onFailed=null, body = null) {
  let fetchParams = {
    method: method.toUpperCase(),
    redirect: 'error'
  };
  if (method.toLowerCase() === 'post' && body) {
    fetchParams.headers = {
        'Content-Type': 'application/json'
    };
    fetchParams.body = JSON.stringify(body);
  }
  fetch(url, fetchParams)
  .then(response => {
    if (response.status === 200) {
      return response.text();
    }
    return Promise.reject(response);
  })
  .then((htmlResponse) => {
    let doc = document.implementation.createHTMLDocument();
    doc.body.innerHTML = htmlResponse;
    let arrayScripts = [].map.call(doc.getElementsByTagName('script'), function(el) {
      return el;
    });
    for (const index in arrayScripts) {
      doc.body.removeChild(arrayScripts[index]);
    }
    elem.innerHTML = doc.body.innerHTML;
    for (const index in arrayScripts) {
      let new_script = document.createElement("script");
      if (arrayScripts[index].src) {
        new_script.src = arrayScripts[index].src;
      } else {
        new_script.innerHTML = arrayScripts[index].innerHTML;
      }
      document.body.appendChild(new_script);
    }
    if (onSucceeded && typeof onSucceeded === "function") {
      onSucceeded(elem);
    }
  })
  .catch((error) => {
    console.error('Error:', error);
    if (onFailed && typeof onFailed === "function") {
      onFailed(elem, error);
    }
  });
}


let _isUserCenterInited = false;
function initUserCenter(realtimeData) {
  if (_isUserCenterInited) {
      return;
  }

  const orderInfo = realtimeData.orderInfo;
  if (!orderInfo) {
    return;
  }
  reportIdentity(orderInfo.user_id, orderInfo.email);
  const userContent = gradioApp().querySelector(".user-content");
  const userInfo = userContent.querySelector("#user_info");
  if (userInfo) {
    userInfo.style.display = "flex";
    //const img = userInfo.querySelector("img");
    //if (img) {
    //    imgExists(orderInfo.picture, img, orderInfo.name);
    //}
    // joinShareGroup(name, imgNode.src);

    if (
      orderInfo.tier.toLowerCase() === "free" ||
      orderInfo.tier.toLowerCase() === "teaser"
    ) {
      const upgradeContent = userContent.querySelector("#upgrade");
      if (upgradeContent) {
        upgradeContent.style.display = "flex";
      }
    }
    changeCreditsPackageLink();
    if (!orderInfo.subscribed && orderInfo.tier.toLowerCase() === "free") {
      setTimeout(openPricingTable, 10000);
    }
  }
  const boostButton = gradioApp().querySelector("#one_click_boost_button");
  let onSucceededCallback = (elem) => {
      elem.style.display = "flex";
  };
  if (boostButton) {
    renderHtmlResponse(
      boostButton,
      "/boost_button/html",
      "GET",
      (onSucceeded = onSucceededCallback),
    );
  }
  _isUserCenterInited = true;
}
// initialize user center
realtimeDataCallbacks.push(initUserCenter);

function initUserCenterMenu() {
  const userAvatar = document.querySelector("#user_info");
  if (!userAvatar) {
    return;
  }
  const content = document.createElement("div");
  content.innerHTML = `
    <v-overlay :value="showUserMenu" z-index="999" @click.native="showUserMenu = false;"></v-overlay>
    <v-menu
      v-model="showUserMenu"
      bottom
      left
      offset-y
      nudge-left="12"
      min-width="280"
      z-index="1000"
      :close-on-click="true"
      :close-on-content-click="false"
      >
        <template v-slot:activator="{ on, attrs }">
          <v-avatar
            color="primary"
            size="46"
            v-bind="attrs"
            v-on="on"
          >
            <img
              :src="userAvatar"
              :alt="userName"
            >
          </v-avatar>
        </template>

        <v-sheet
          elevation="1"
          rounded
          id="user_center_menu"
        >
          <div class="d-flex flex-row px-3 pt-3">
            <v-avatar class="d-flex">
              <img
                :src="userAvatar"
                :alt="userName"
              >
            </v-avatar>
            <div class="d-flex flex-column ml-2">
              <span v-if="userName!=userEmail" class="d-flex">{{ userName }}</span>
              <span class="d-flex">{{ userEmail }}</span>
            </div>
          </div>
          <v-divider
            class="my-2"
            style="border-top: 1px solid #636363;"
          ></v-divider>
          <v-list>
            <v-list-item @click="redirectToUserCenter">
              <v-list-item-icon>
                <v-icon>build</v-icon>
              </v-list-item-icon>
              <v-list-item-content>
                <v-list-item-title>User Center</v-list-item-title>
              </v-list-item-content>
            </v-list-item>
            <v-list-item @click="redirectToComfy">
              <v-list-item-icon>
                <v-icon>account_tree</v-icon>
              </v-list-item-icon>
              <v-list-item-content>
                <v-list-item-title>ComfyUI
                  <v-chip
                    class="ml-2"
                    color="#ff9800d4"
                    small
                  >
                    Free Alpha
                  </v-chip>
                </v-list-item-title>
              </v-list-item-content>
            </v-list-item>
            <v-list-item @click="cancelSubscription">
              <v-list-item-icon>
                <v-icon>highlight_off</v-icon>
              </v-list-item-icon>
              <v-list-item-content>
                <v-list-item-title>Cancel Subscription</v-list-item-title>
              </v-list-item-content>
            </v-list-item>
            <v-list-item @click="logout">
              <v-list-item-icon>
                <v-icon>logout</v-icon>
              </v-list-item-icon>
              <v-list-item-content>
                <v-list-item-title>Logout</v-list-item-title>
              </v-list-item-content>
            </v-list-item>
          </v-list>
        </v-sheet>
      </v-menu>
    `;
  userAvatar.appendChild(content);

  const style = document.createElement("style");
  style.innerHTML = `
    `;
  document.head.appendChild(style);

  new Vue({
    el: "#user_info",
    vuetify: new Vuetify({
      theme: { dark: true },
    }),
    data() {
      return {
        showUserMenu: false,
        userAvatar: "",
        userName: "",
        userEmail: "",
      };
    },
    methods: {
      getAvatar(url, name, callback) {
        const img = new Image();
        img.onerror = () => {
          const imgSrc = `https://ui-avatars.com/api/?name=${name}&background=random&format=svg`;
          callback(imgSrc);
          joinShareGroup(name, imgSrc);
        };
        img.onload = () => {
          callback(url);
          joinShareGroup(name, url);
        };
        img.src = url;
      },
      updateUserInfo(realtimeData) {
        const orderInfo = realtimeData.orderInfo;
        this.userEmail = orderInfo.email;
        this.userName = orderInfo.name;
        this.getAvatar(orderInfo.picture, orderInfo.name, (url) => {
          this.userAvatar = url;
        });
      },
      redirectToUserCenter() {
        window.location.href = "/user";
      },
      redirectToComfy() {
        const comfyInfo = channelResult.sub_pages.find(item => item.name.toLowerCase() === "comfyui");
        if (comfyInfo) {
          window.open(comfyInfo.url, "_blank");
        }
      },
      cancelSubscription() {
        window.location.href = "/user#/billing?cancel_subscription=true";
      },
      logout() {
        document.cookie = "auth-session=;";
        window.location.href = "/api/logout";
      },
    },
    mounted() {
      realtimeDataCallbacks.push(this.updateUserInfo);
    },
  });
}

onUiLoaded(initUserCenterMenu);
