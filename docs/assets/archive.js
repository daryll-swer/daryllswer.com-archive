(() => {
  function sectionUrl(anchor) {
    const url = new URL(window.location.href);
    url.hash = anchor;
    return url.toString();
  }

  document.addEventListener("click", async (event) => {
    const button = event.target.closest(".heading-copy");
    if (!button) {
      return;
    }
    const anchor = button.getAttribute("data-anchor");
    if (!anchor) {
      return;
    }
    const text = sectionUrl(anchor);
    try {
      await navigator.clipboard.writeText(text);
      button.classList.add("copied");
      button.textContent = "Copied";
      window.setTimeout(() => {
        button.classList.remove("copied");
        button.textContent = "Copy";
      }, 1600);
    } catch (_) {
      window.location.hash = anchor;
    }
  });
})();
