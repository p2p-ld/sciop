// Transform a "success: true" message to just be "success" or "failure"
htmx.on("htmx:afterRequest", (e) => {
  console.log(e)
  console.log(e.target.classList)
  if (e.target.classList.contains('success-button')){
    console.log('hey!!!')
    e.target.innerHTML = e.detail.successful ? "Success!" : "Error!"
  }
})