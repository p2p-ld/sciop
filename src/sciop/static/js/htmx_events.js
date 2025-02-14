// Transform a "success: true" message to just be "success" or "failure"
htmx.on("htmx:afterRequest", (e) => {
  if (e.target.classList.contains('success-button')){
    e.target.innerHTML = e.detail.successful ? "Success!" : "Error!"
  }
})

// Detect enter key without event filters
document.addEventListener("keyup", (e) => {
  if (e.key === "Enter") {
    let elt = htmx.closest(document.activeElement, ".enter-trigger");
    if (elt !== null){
      htmx.trigger(elt, "enterKeyUp");
    }
  }
})