function darkmode(){
  const btn = document.querySelector("#theme-button");
  const prefersDarkScheme = window.matchMedia("(prefers-color-scheme: dark)");
  const storedTheme = localStorage.getItem("theme");
  let currentTheme;

  function setTheme(theme){
    if (theme === "dark"){
      document.body.classList.remove("light-theme");
      btn.ariaPressed = "false"
      btn.ariaLabel = "Toggle the theme to light mode"
      btn.classList.remove("light")
    } else {
      document.body.classList.add("light-theme");
      btn.ariaPressed = "true"
      btn.ariaLabel = "Toggle the theme to dark mode"
      btn.classList.add("light")
    }
    localStorage.setItem("theme", theme);
  }

  if (storedTheme === null) {
    currentTheme = prefersDarkScheme.matches ? "dark" : "light";
  } else {
    currentTheme = storedTheme;
  }

  setTheme(currentTheme);
  btn.checked = currentTheme === "light";

  btn.addEventListener("click", function (e) {
    if (btn.ariaPressed === "true") {
      setTheme("dark");
    } else {
      setTheme("light");
    }
  });
}

// https://stackoverflow.com/a/61511955/13113166
// want to fire dark mode detection as soon as checkbox exists, not after full page is loaded,
// to avoid flashing dark/light on navigation
function waitForElm(selector) {
    return new Promise(resolve => {
        if (document.querySelector(selector)) {
            return resolve(document.querySelector(selector));
        }

        const observer = new MutationObserver(mutations => {
            if (document.querySelector(selector)) {
                observer.disconnect();
                resolve(document.querySelector(selector));
            }
        });

        // If you get "parameter 1 is not of type 'Node'" error, see https://stackoverflow.com/a/77855838/492336
        observer.observe(document.documentElement, {
            childList: true,
            subtree: true
        });
    });
}

waitForElm("#theme-button").then(() => darkmode())

// Don't animate background color changes and the toggle button when first loading the page
window.addEventListener("load", () => {
  document.body.classList.remove('preload');
  const slider = document.querySelector("#option-darkmode-slider");
  slider.classList.remove('preload');
});

