const SCROLL_KEY = "timebox-scroll-state";

function saveScrollPosition() {
  const payload = {
    path: window.location.pathname,
    scrollY: window.scrollY,
    createdAt: Date.now(),
  };
  sessionStorage.setItem(SCROLL_KEY, JSON.stringify(payload));
}

function restoreScrollPosition() {
  const raw = sessionStorage.getItem(SCROLL_KEY);
  if (!raw || window.location.hash) {
    return;
  }

  try {
    const saved = JSON.parse(raw);
    const isRecent = Date.now() - saved.createdAt < 15000;
    if (saved.path === window.location.pathname && isRecent) {
      window.scrollTo({ top: saved.scrollY, behavior: "auto" });
    }
  } catch (_error) {
    // Ignore malformed session data and continue with default scroll behavior.
  } finally {
    sessionStorage.removeItem(SCROLL_KEY);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  restoreScrollPosition();

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    saveScrollPosition();
  });
});
