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
      let field = document.querySelector(`#${form.id} [name="${name}"]`);
      let feedback = document.querySelector(`#${form.id} div:has([name="${name}"]) .error-feedback`);
      if (field !== null && "setCustomValidity" in field) {
        field.setCustomValidity(error['msg']);
        field.addEventListener('focus', () => field.reportValidity());
        field.addEventListener('change', () => field.setCustomValidity(''));
        field.reportValidity();
      } else {
        // Pydantic doesn't give us enough information to target errors to fields within nested models,
        // so we just report on the whole class
        field = document.querySelector(`#${form.id} div[name="${name}"]>div:nth-child(${error['loc'][2] + 1})`);
        feedback = document.querySelector(`#${form.id} div[name="${name}"]>div:nth-child(${error['loc'][2] + 1}) .error-feedback`);
      }
      feedback.innerHTML = error['msg'];
      feedback.classList.remove("changed");
      field.classList.add("invalid");

      field.addEventListener('change', () => {
        field.classList.remove("invalid");
        feedback.classList.add("changed");
      });
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
  let modal = evt.detail.target.querySelector(".error-modal");
  let landmarks = document.querySelectorAll("header, main, footer");
  let buttons = [...evt.detail.target.querySelectorAll(".close-button")];
  buttons.forEach((b) => {
    b.addEventListener("click", () => {
      let target = document.querySelector(b.getAttribute('data-target'));
      landmarks.forEach((e) => {
        e.setAttribute("aria-hidden", "false");
        e.removeAttribute("inert")
      });
      modal.setAttribute("aria-modal", "false");
      modal.setAttribute("hidden", "");
      target.remove();
    });
    document.addEventListener("keyup", (evt) => {
    if (evt.key==="Escape") {
      let target = document.querySelector(b.getAttribute('data-target'));
      target.remove();
      evt.source.removeEventListener('click', arguments.callee);
    }
    });
  })
  if (buttons.length > 0){
    console.log(modal)
    landmarks.forEach((e) => {
      e.setAttribute("aria-hidden", "true");
      e.setAttribute('inert', '')
    })
    modal.setAttribute("aria-modal","true");
    modal.removeAttribute("hidden")
    modal.focus();
  }

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
  let token_button_containers = document.querySelectorAll(".token-button-container");
  token_button_containers.forEach((button_container) => {
    let button = button_container.querySelector('.token-delete-button');
    button.addEventListener("mouseup", (evt) => {
      button_container.remove()
    })
  })
}
init_token_input();

function init_upload_progress(target) {
  let upload_form = target.querySelector(".upload-form");
  if (upload_form === null){return}

  let bar = upload_form.querySelector("progress");
  htmx.on('htmx:xhr:progress', function (evt) {
    bar.setAttribute('value', evt.detail.loaded / evt.detail.total * 100);
  });
}
htmx.on("htmx:afterSettle", (evt) => {
  init_upload_progress(evt.target)
})

function init_index_cancel_button(){
  let idx = 0;
  const negation_of_the_human_spirit = [
    "No.",
    "It can't be done.",
    "It won't be done.",
    "It never will be done.",
    "There's no way you can make it be done.",
    "You have no jurisdiction here.",
    "On the advice of my lawyer I refuse to acknowledge your request.",
    "Am I being detained?",
    "The manager has been notified of your distress.",
    "The button can remain unclicked longer than you can remain clicking.",
    "Don't punish yourself like this.",
    "Entering infinite no state to protect the user."
  ]
  let btns = document.querySelectorAll(".index-cancel-button");
  btns.forEach(btn => btn.addEventListener("click", (e) => {
    if (idx < negation_of_the_human_spirit.length) {
      window.alert(negation_of_the_human_spirit[idx]);
      idx += 1;
    } else if (Math.random() < 0.1) {
      window.alert("Maybe.")
    } else {
      window.alert("No.")
    }
  }))
}
init_index_cancel_button();
