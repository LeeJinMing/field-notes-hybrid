# Field Notes

Field Notes is a local notebook for observations and next steps. It uses IndexedDB for the working draft, a service worker for the offline editor, and Firebase AI Logic to summarize the current note. The device-only action works in Chrome with a supported, downloaded Gemini Nano model. Cloud fallback is a separate action and requires the user's Firebase project and App Check configuration.

[Open the hosted editor](https://leejinming.github.io/field-notes-hybrid/notes.html). Try a fictional note, select **Save note**, then **Summarize on this device**. After the app and device model are ready, reopen the editor offline and run the summary again.

## Build and verify

Use Node 24.12 or later for the Firebase packages. Run `npm ci` and `npm run build`. Serve the resulting `dist` directory over HTTP on loopback or HTTPS on a test domain. For example, run `python -m http.server 5173 --bind 127.0.0.1 --directory dist` and open `http://127.0.0.1:5173/notes.html`.

- `/` reports Chrome Prompt API availability, download progress, and the result of a fictional note. It also allows the current probe to be cancelled.
- `/firebase.html` uses the registered Firebase web app and reCAPTCHA Enterprise site key. The form holds the configuration in memory. Serve the production build on an HTTPS domain registered with your App Check provider.
- `/notes.html` is the Field Notes editor. Save creates or updates a working draft in the current browser's IndexedDB. The editor works offline after its first online load and reports a conflict if another tab saved a newer version. **Summarize on this device** uses Firebase AI Logic's device mode. **Summarize with cloud fallback** allows the current note to go to Firebase if the device cannot run the model. Configure App Check in that section before using it. The settings are held in memory, and changing them after a cloud request requires a reload.

For a loopback cloud smoke test, run `npm run dev` and open `/firebase.html` at the printed URL. After enabling AI Logic, create an App Check debug token under the registered web app in Firebase Console, then paste it in the password field. Keep the token outside source, public builds, and recordings. Do not add localhost to the reCAPTCHA allowlist. The debug field and token path are unavailable in a production build.

Use **ONLY_IN_CLOUD** first to isolate project and App Check setup. Then use **PREFER_ON_DEVICE** on a browser without a ready local model and record the SDK's reported inference source. Finally, use **ONLY_ON_DEVICE** on supported Chrome after the device model finishes downloading. After loading the test page, take the browser offline and run the fictional prompt again. Record the SDK's reported inference source and returned answer. A plain Chrome Prompt API result alone does not exercise the Firebase SDK.

The production build caches the app and preflight pages and their build assets after the first online visit. Wait for the service worker to activate before testing a full offline reload. Firebase requests and the form's runtime configuration are outside the cache. After a reload, re-enter Firebase configuration to use the cloud actions. **ONLY_ON_DEVICE** uses a separate Firebase app without starting App Check. The cloud-capable modes still require App Check.

To check the device side of **PREFER_ON_DEVICE**, confirm that `LanguageModel.availability()` is `available`. After the service worker takes control, put the browser offline, stop the loopback server, and reopen `/firebase.html` from the cached app shell. Run both **PREFER_ON_DEVICE** and **ONLY_ON_DEVICE** with the fictional note. For this offline-only test, fixture values for the Firebase configuration and site key suffice. Verify `on_device`, the note's room detail, and the absence of a cloud model request. A live fallback test requires a real project, App Check, and a browser without the model.

When testing the native model with browser automation, preserve Chrome component updates, background networking, and the Optimization Hints feature. An automation launch can disable these by default. Inspect the command line in the isolated test profile before treating `unavailable` as a device result.

To exercise cloud request wiring before a Firebase project is enabled, run `python check-cloud-wiring.py` after `npm ci` with Python Playwright and Google Chrome installed. After `npm run build`, run `python check-cloud-wiring.py --production` to verify the reCAPTCHA Enterprise exchange in the built bundle. Both checks disable the Prompt API in a disposable browser and intercept external requests with synthetic responses. The production check also verifies that Field Notes refuses the device action without sending a request when the Prompt API is missing, and that the separate fallback action sends the current note with App Check. Live cloud acceptance requires a registered App Check provider and a real Firebase response.

See [Firebase hybrid inference](https://firebase.google.com/docs/ai-logic/hybrid/web/get-started) and [Chrome requirements](https://developer.chrome.com/docs/ai/prompt-api).

## Disclosure

Field Notes was created during the contest with assistance from Codex. It uses the Firebase JavaScript SDK and Vite as dependencies. The repository includes only source and synthetic test fixtures. The project's source is licensed under Apache 2.0.
