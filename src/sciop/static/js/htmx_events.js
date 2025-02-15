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
});

// Error reporting for forms
htmx.on("htmx:responseError", (e) => {
  const xhr = e.detail.xhr;
  if (xhr.status == 422) {
    const errors = JSON.parse(xhr.responseText)["detail"];
    const form = e.detail.target;
    const feedbacks = document.querySelectorAll(`#${form.id} .error-feedback`);
    feedbacks.forEach(f => f.innerHTML = '');

    for (error of errors){
      let name = error['loc'][1];
      const field = document.querySelector(`#${form.id} [name="${name}"]`);
      const feedback = document.querySelector(`#${form.id} div:has([name="${name}"]) .error-feedback`);
      field.setCustomValidity(error['msg']);
      feedback.innerHTML = error['msg'];
      feedback.classList.remove("changed");
      field.classList.add("invalid");
      field.addEventListener('focus', () => field.reportValidity());
      field.addEventListener('change', () => {
        field.setCustomValidity('');
        field.classList.remove("invalid");
        feedback.classList.add("changed");
      });
      field.reportValidity();
    }
  } else {
    // Handle the error some other way
    console.error(xhr.responseText);
  }
})

htmx.on("htmx:beforeOnLoad", (evt) => {
  if (evt.detail.xhr.status >= 400 && evt.detail.xhr.status !== 422) {
      evt.detail.shouldSwap = true;
  }
})

// Close buttons on modals
htmx.on("htmx:afterSwap", (evt) => {
  if (evt.detail.xhr.status<400){ return }
  let buttons = [...evt.detail.target.querySelectorAll(".close-button")];
  buttons.forEach((b) => {
    b.addEventListener("click", () => {
      let target = document.querySelector(b.getAttribute('data-target'));
      target.remove();
  })})
})