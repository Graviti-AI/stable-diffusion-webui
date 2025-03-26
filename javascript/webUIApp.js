const webUIApp = {
    updateFavoriteCheckpoints() {
        const refreshButton = gradioApp().getElementById("refresh_sd_model_checkpoint_dropdown");
        if (refreshButton) {
            refreshButton.click();
        }
    },
};

onUiLoaded(() => {
    window.webUIApp = webUIApp;
});
