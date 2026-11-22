if (import.meta.env.PROD && "serviceWorker" in navigator) {
  const worker = new URL("./app-shell-worker.js", document.baseURI);
  navigator.serviceWorker.register(worker).catch(error => {
    console.warn("Offline app shell unavailable:", error.message);
  });
}
