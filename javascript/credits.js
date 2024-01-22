function initCreditsBar() {
    const creditBar = document.querySelector("#user-credits-app");
    if (!creditBar) {
        return;
    }
    const content = document.createElement("div");
    content.style = "width: 100%;";
    content.innerHTML = `
        <v-progress-linear :value="percentage" color="purple" height="13" rounded>
            <strong style="font-size: 13px;"> Credits: {{ used }} / {{ permitted }}</strong>
        </v-progress-linear>
    `;
    creditBar.appendChild(content);

    const style = document.createElement("style");
    style.innerHTML = `
        .v-progress-linear__determinate {
            background-color: var(--primary-600);
        }
        .v-progress-linear__background {
            background-color: var(--primary-400);
        }
    `;
    document.head.appendChild(style);

    new Vue({
        el: "#user-credits-app",
        vuetify: new Vuetify({
            theme: { dark: true },
        }),
        data() {
            return {
                permitted: 0,
                used: 0,
            };
        },
        computed: {
            percentage() {
                return (this.used / this.permitted) * 100;
            },
        },
        methods: {
            async queryOrderInfo(interval) {
                while (true) {
                    const response = await fetchGet("/api/order_info");
                    if (response.ok) {
                        const content = await response.json();
                        this.updateFromOrderInfo(content);
                    }
                    await PYTHON.asyncio.sleep(interval * 1000);
                }
            },
            updateFromOrderInfo(response) {
                let permitted = 0;
                let used = 0;
                response.inference_usage.forEach((item) => {
                    permitted += item.permitted;
                    used += item.used;
                });
                this.permitted = permitted;
                this.used = used;
            },
        },
        mounted() {
            this.queryOrderInfo(10);
        },
    });
}

onUiLoaded(initCreditsBar);
