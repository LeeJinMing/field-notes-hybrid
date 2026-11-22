import "./offline-shell.mjs";

const status = document.querySelector("#status");
const result = document.querySelector("#result");
const probe = document.querySelector("#probe");
const cancel = document.querySelector("#cancel");
const deviceModel = globalThis.LanguageModel;
let controller;

async function refresh() {
  try {
    const availability = deviceModel ? await deviceModel.availability() : "Prompt API unavailable";
    status.textContent = availability;
    probe.disabled = !deviceModel || availability === "unavailable" || Boolean(controller);
    return availability;
  } catch (error) {
    status.textContent = error.message;
    probe.disabled = true;
  }
}

cancel.addEventListener("click", () => controller?.abort());
probe.addEventListener("click", async () => {
  const request = new AbortController();
  controller = request;
  probe.disabled = true;
  cancel.disabled = false;
  result.textContent = "";
  status.textContent = "Preparing Chrome's model…";
  let session;
  try {
    session = await deviceModel.create({
      signal: request.signal,
      monitor(model) {
        model.addEventListener("downloadprogress", event => {
          status.textContent = `Downloading model: ${Math.round(event.loaded * 100)}%`;
        });
      },
    });
    status.textContent = "Running on this device…";
    result.textContent = await session.prompt(
      "Summarize in one sentence: Move the fictional Tuesday rehearsal to Room B.",
      { signal: request.signal },
    );
  } catch (error) {
    result.textContent = request.signal.aborted ? "Probe cancelled." : `${error.name}: ${error.message}`;
  } finally {
    session?.destroy();
    controller = undefined;
    cancel.disabled = true;
    await refresh();
  }
});

await refresh();
