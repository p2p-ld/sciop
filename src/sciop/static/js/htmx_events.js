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

// Token input field
function addToken(e){
  if (e.key !== "Enter"){ return }
  e.preventDefault()
  let container = document.querySelector(e.target.getAttribute("data-tokens-container"));

  // Ignore existing tags
  let input_children = container.querySelectorAll("input");
  let existing_tags = [...input_children].map((child) => child.value);
  if (existing_tags.includes(e.target.value)){return}

  // hidden input element representing the token in the form
  let token = document.createElement("input");
  token.setAttribute("name", e.target.name);
  token.setAttribute("value", e.target.value);
  token.value = e.target.value;
  token.setAttribute("readonly", "readonly");
  token.classList.add("hidden");

  // visible token
  let token_span = document.createElement("span");
  token_span.innerHTML = e.target.value;
  token_span.classList.add("token")

  // delete button
  let token_container = document.createElement("div");
  token_container.classList.add("token-button-container");
  let delete_button = document.createElement("button");
  delete_button.setAttribute("type", "button");
  delete_button.innerHTML = "x";
  delete_button.classList.add("delete-button", "token-delete-button");
  delete_button.addEventListener("mouseup", (e) => {
    token_container.remove()
  });

  // combine and add
  token_container.appendChild(token);
  token_container.appendChild(token_span);
  token_container.appendChild(delete_button);
  container.appendChild(token_container);

  // clear input
  e.target.value = "";
  e.target.focus();
}

function init_token_input(){
  let token_inputs = document.querySelectorAll(".form-tokens");
  token_inputs.forEach((e) => {
    e.addEventListener("keyup", addToken)
  })
}
init_token_input();
