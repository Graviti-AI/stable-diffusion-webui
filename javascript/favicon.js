class FaviconHandler {
  static setFavicon() {
    const link = document.createElement('link');
    link.rel = 'icon';
    link.type = 'image/svg+xml';
    link.href =
      'https://images.squarespace-cdn.com/content/v1/6411cba29f7f4b4a7e9609c8/f86d5718-8b9c-444b-acd2-120472d8f931/favicon.ico?format=100w';
    document.getElementsByTagName('head')[0].appendChild(link);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  FaviconHandler.setFavicon();
});
