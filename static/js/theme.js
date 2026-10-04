// Runs in <head> before the page paints, so the saved theme applies without a flash.
(function () {
    var theme = null;
    try { theme = localStorage.getItem('theme'); } catch (e) { /* storage blocked: use default */ }
    var dark = theme === 'dark' || (theme === null && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('dark', dark);
})();
