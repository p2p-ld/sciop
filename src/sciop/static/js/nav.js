// close the menu when switching to the wide layout
window.matchMedia("(max-width: 768px)").addEventListener("change", (e) => {
  const menu = document.querySelector("#nav-menu");
  if (!e.matches && menu && menu.matches(":popover-open")) {
    menu.hidePopover();
  }
});
