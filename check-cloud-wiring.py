"""Exercise the real Firebase Web SDK against browser-local response fixtures."""

import argparse
import json
import re
import socket
import subprocess
from pathlib import Path
from time import monotonic, sleep
from urllib.parse import urlsplit
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright


CONFIG = {"apiKey": "fixture-api-key", "projectId": "fixture-project", "appId": "1:123:web:456"}
DEBUG_TOKEN = "fixture-debug-token"
APP_CHECK_TOKEN = "fixture-app-check-token"
SITE_KEY = "fixture-site-key"
ENTERPRISE_TOKEN = "fixture-enterprise-token"
NOTE = "Move Tuesday rehearsal to Room B and bring the printed score."
RECAPTCHA_FIXTURE = """
let widget;
globalThis.grecaptcha = { enterprise: {
  ready(callback) { callback(); },
  render(container, options) {
    if (!document.getElementById(container) || options.sitekey !== 'fixture-site-key') {
      throw new Error('Unexpected reCAPTCHA widget');
    }
    widget = options;
    return 1;
  },
  async execute(id, options) {
    if (id !== 1 || options.action !== 'fire_app_check') throw new Error('Unexpected attestation action');
    widget.callback();
    return 'fixture-enterprise-token';
  }
} };
"""


def check(browser, origin, mode, *, production, reject_cloud=False, editor=False, provider="developer"):
    context = browser.new_context(service_workers="block")
    calls = []
    exchange = "exchangeRecaptchaEnterpriseToken" if production else "exchangeDebugToken"

    def route_request(route):
        request = route.request
        address = urlsplit(request.url)
        if f"{address.scheme}://{address.netloc}" == origin:
            return route.continue_()

        if production and address.hostname == "www.google.com" and address.path == "/recaptcha/enterprise.js":
            calls.append(("recaptcha-enterprise",))
            return route.fulfill(content_type="text/javascript", body=RECAPTCHA_FIXTURE)

        if address.hostname == "content-firebaseappcheck.googleapis.com":
            if not address.path.endswith(f":{exchange}"):
                calls.append(("unexpected-app-check", address.path))
                return route.abort()
            calls.append(("app-check", request.post_data_json, address.path))
            return route.fulfill(json={"token": APP_CHECK_TOKEN, "ttl": "600s"})

        if (address.hostname == "firebasevertexai.googleapis.com"
                and address.path.endswith(":generateContent")):
            calls.append(("firebase-ai", request.all_headers(), request.post_data_json, address.path))
            if reject_cloud:
                return route.fulfill(status=403, json={"error": {"code": 403, "message": "Fixture denied access"}})
            candidate = {"content": {"role": "model", "parts": [{"text": NOTE}]}, "finishReason": "STOP"}
            return route.fulfill(json={"candidates": [candidate]})

        return route.abort()

    try:
        context.route("**/*", route_request)
        page = context.new_page()
        page.goto(f"{origin}/{'notes.html' if editor else 'firebase.html'}")
        assert page.evaluate("typeof globalThis.LanguageModel === 'undefined'")
        if editor:
            note = page.get_by_label("Note", exact=True)
            note.fill(NOTE)
            page.get_by_role("button", name="Summarize on this device").click()
            expect(page.locator("#ai-status")).to_contain_text("not available")
            assert not calls, calls
            page.get_by_text("Cloud fallback settings", exact=True).click()
            page.get_by_label("Cloud backend").select_option(provider)
            page.get_by_label("Firebase web configuration").fill(json.dumps(CONFIG))
            page.get_by_label("App Check site key").fill(SITE_KEY)
            expect(page.locator("#cloud-debug-controls")).to_be_hidden()
            page.get_by_role("button", name="Summarize with cloud fallback").click()
            expect(page.locator("#ai-status")).to_have_text("Summarized by Firebase AI Logic in the cloud.")
            expect(page.locator("#summary-text")).to_have_text(NOTE)
            note.fill("Edited after summarization.")
            expect(page.locator("#summary-text")).to_be_hidden()
        else:
            output = page.locator("#output")
            expect(output).to_have_text("SDK loaded.")
            page.locator("#config").fill(json.dumps(CONFIG))
            page.locator("#site").fill(SITE_KEY)
            debug_field = page.locator("#debug-token")
            if production:
                expect(debug_field).to_be_hidden()
                debug_field.evaluate("(field, token) => field.value = token", DEBUG_TOKEN)
            else:
                debug_field.fill(DEBUG_TOKEN)
            page.locator("#mode").select_option(mode)
            page.get_by_label("Cloud backend").select_option(provider)
            page.get_by_role("button", name="Run", exact=True).click()
            if reject_cloud:
                expect(output).to_contain_text("Fixture denied access")
                assert "in_cloud" not in output.inner_text()
            else:
                expect(output).to_have_text(re.compile(r"^in_cloud\s+" + re.escape(NOTE) + "$"))
        expected_calls = ["app-check", "firebase-ai"]
        if production:
            expected_calls.insert(0, "recaptcha-enterprise")
        assert [entry[0] for entry in calls] == expected_calls, calls
        _, token_request, token_path = calls[-2]
        expected_token = ({"recaptcha_enterprise_token": ENTERPRISE_TOKEN} if production
                          else {"debug_token": DEBUG_TOKEN})
        assert token_request == expected_token
        assert token_path == f"/v1/projects/{CONFIG['projectId']}/apps/{CONFIG['appId']}:{exchange}"
        _, headers, prompt, model_path = calls[-1]
        assert headers["x-firebase-appcheck"] == APP_CHECK_TOKEN
        assert headers["x-goog-api-key"] == CONFIG["apiKey"]
        assert ("hybrid" in headers["x-goog-api-client"].split()) == (mode == "PREFER_ON_DEVICE")
        assert NOTE in prompt["contents"][0]["parts"][0]["text"]
        assert ("/publishers/google/models/" in model_path) == (provider == "agent-platform")
        if editor and provider == "agent-platform":
            page.get_by_label("Cloud backend").select_option("developer")
            page.get_by_role("button", name="Summarize with cloud fallback").click()
            expect(page.locator("#summary-text")).to_have_text(NOTE)
            assert [entry[0] for entry in calls] == [*expected_calls, "firebase-ai"], calls
            assert "/publishers/google/models/" not in calls[-1][-1]
            assert calls[-1][1]["x-firebase-appcheck"] == APP_CHECK_TOKEN
            assert "Edited after summarization." in calls[-1][2]["contents"][0]["parts"][0]["text"]
            page.get_by_label("App Check site key").fill("different-site-key")
            page.get_by_role("button", name="Summarize with cloud fallback").click()
            expect(page.locator("#ai-status")).to_contain_text("Reload to change projects or App Check settings")
            expect(note).to_have_value("Edited after summarization.")
            assert [entry[0] for entry in calls] == [*expected_calls, "firebase-ai"], calls
            page.get_by_role("button", name="Save note", exact=True).click()
            expect(page.locator("#status")).to_have_text("Saved on this device.")
            page.reload()
            expect(note).to_have_value("Edited after summarization.")
            assert [entry[0] for entry in calls] == [*expected_calls, "firebase-ai"], calls
        build = "production" if production else "development"
        if editor:
            print(f"PASS production Field Notes {provider}: no cloud request from device action; App Check on explicit fallback")
        else:
            print(f"PASS {build} {provider} {mode} {'403' if reject_cloud else 'in_cloud'} (fixture response)")
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production", action="store_true", help="Serve the production bundle after npm run build")
    production = parser.parse_args().production
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    root = Path(__file__).resolve().parent
    origin = f"http://127.0.0.1:{port}"
    command = ["node", "node_modules/vite/bin/vite.js"]
    if production:
        command.append("preview")
    command.extend(["--host", "127.0.0.1", "--port", str(port), "--strictPort"])
    server = subprocess.Popen(command, cwd=root)
    try:
        deadline = monotonic() + 15
        while True:
            try:
                with urlopen(f"{origin}/firebase.html", timeout=1):
                    break
            except URLError:
                if server.poll() is not None or monotonic() >= deadline:
                    raise
                sleep(0.2)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", args=["--disable-features=AIPromptAPI"])
            try:
                check(browser, origin, "ONLY_IN_CLOUD", production=production)
                check(browser, origin, "ONLY_IN_CLOUD", production=production, provider="agent-platform")
                check(browser, origin, "PREFER_ON_DEVICE", production=production)
                check(browser, origin, "PREFER_ON_DEVICE", production=production, reject_cloud=True)
                if production:
                    check(browser, origin, "PREFER_ON_DEVICE", production=True, editor=True)
                    check(browser, origin, "PREFER_ON_DEVICE", production=True, editor=True, provider="agent-platform")
            finally:
                browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    main()
