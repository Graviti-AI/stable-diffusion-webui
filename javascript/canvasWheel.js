// The Forge canvas zooms its image on wheel, preventing the default; the perfect scrollbar of the page, which
// scrolls on wheel by itself, would scroll it as well. A wheel prevented in a canvas goes no further.
onUiLoaded(() => {
    for (const container of gradioApp().querySelectorAll('.forge-container')) {
        container.addEventListener('wheel', (e) => {
            if (e.defaultPrevented) {
                e.stopPropagation();
            }
        });
    }
});
