import { infer, LOCAL_DEBUG, readFirebaseConfig } from "./firebase-inference.mjs";
import "./offline-shell.mjs";

const field = id => document.getElementById(id);
const button = field("run");
const output = field("output");
if (LOCAL_DEBUG) field("debug-controls").hidden = false;

button.addEventListener("click", async () => {
  button.disabled = true;
  output.textContent = "Running…";
  try {
    const { source, text } = await infer({
      config: readFirebaseConfig(field("config").value),
      mode: field("mode").value,
      provider: field("provider").value,
      siteKey: field("site").value.trim(),
      debugToken: LOCAL_DEBUG ? field("debug-token").value.trim() : "",
      prompt: "Summarize this fictional note in one sentence: Move Tuesday rehearsal to Room B and bring the printed score.",
      progress: progress => {
        output.textContent = `Downloading device model: ${Math.round(progress * 100)}%`;
      },
      deviceReady: () => { output.textContent = "Running on device…"; },
    });
    output.textContent = (source ?? "Source unknown") + "\n" + text;
  } catch (error) {
    output.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
output.textContent = "SDK loaded.";
