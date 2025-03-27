# Error Handling

<div class="big-emphasis" markdown="1">

*this a placeholder, help us out by [making a pull request](/docs/contributing.md)
to improve the docs <3*

</div>

## Modals

(todo: link to code when we figure out how autodocs in mkdocs works)

When requests are made from the web interface using HTMX, they have a
`HX-Request: true` header. 
When the server returns an HTTP status code above 400, 
an exception handler middleware uses the `HX-Reswap` and `HX-Retarget`
[response headers](https://htmx.org/reference/#response_headers)
to retarget that to a model alert to a hidden dom element `#error-modal-container`.

Clientside, error events are handled 
- First with a `htmx:beforeOnLoad` handler that forces htmx to reswap the error
  (by default, errors are not swapped)
- Second, an `htmx:afterSwap` handler adds event listeners for the close buttons
  and set the modal as being in focus for screen readers.

Once the modal has no more children, it returns to being hidden using CSS selectors.

## Form Validation and 422's

422 errors are handled as a special case by the client,
as a result, 422 errors should not be used for reporting errors
with an `HTTPException`. 

(todo: document how the form validation error handling works)

