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
          callback(
            `https://ui-avatars.com/api/?name=${name}&background=random&format=svg`,
          );
        };
        img.onload = () => {
          callback(url);
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
