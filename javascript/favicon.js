class FaviconHandler {
  static setFavicon() {
    const link = document.createElement('link');
    link.rel = 'icon';
    link.type = 'image/svg+xml';
    link.href = 'https://diffus-public-static-assets.s3.amazonaws.com/logos/diffus/favicon.ico';
    document.getElementsByTagName('head')[0].appendChild(link);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  FaviconHandler.setFavicon();
});
