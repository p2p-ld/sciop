// Transform a "success: true" message to just be "success" or "failure"
htmx.on("htmx:afterRequest", (e) => {
  console.log(e)
  console.log(e.detail.target.classList)
  if (e.detail.target.classList.contains('success-button')){
    console.log('hey!!!')
    e.detail.target.innerHTML = e.detail.successful ? "Success!" : "Error!"
  }
})