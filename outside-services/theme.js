// The status page follows the device's light or dark choice: the design system's tokens set dark with data-theme.
if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
  document.documentElement.setAttribute("data-theme", "dark");
}
