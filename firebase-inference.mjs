import { initializeApp, deleteApp } from "firebase/app";
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from "firebase/app-check";
import { AgentPlatformBackend, getAI, getGenerativeModel, GoogleAIBackend, InferenceMode } from "firebase/ai";

export const LOCAL_DEBUG = import.meta.env.DEV && ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
let cloudConfig;
let cloudApp;

export function readFirebaseConfig(value) {
  const config = JSON.parse(value);
  if (!config?.apiKey || !config.projectId || !config.appId) {
    throw new Error("Provide a Firebase web configuration.");
  }
  return config;
}

async function getAttestedApp(config, siteKey, debugToken) {
  if (!siteKey) throw new Error("Provide the App Check site key for cloud inference.");
  if (LOCAL_DEBUG && !debugToken) throw new Error("Provide an App Check debug token registered for this web app.");
  const identity = JSON.stringify([config, siteKey, LOCAL_DEBUG ? debugToken : ""]);
  if (cloudApp && cloudConfig !== identity) throw new Error("Reload to change projects or App Check settings.");
  if (cloudApp) return cloudApp;

  const app = initializeApp(config);
  try {
    if (LOCAL_DEBUG) globalThis.FIREBASE_APPCHECK_DEBUG_TOKEN = debugToken;
    initializeAppCheck(app, { provider: new ReCaptchaEnterpriseProvider(siteKey), isTokenAutoRefreshEnabled: true });
    cloudApp = app;
    cloudConfig = identity;
    return app;
  } catch (error) {
    await deleteApp(app);
    throw error;
  }
}

export async function infer({ config, mode, prompt, siteKey = "", debugToken = "", provider = "developer", progress, deviceReady }) {
  const inferenceMode = InferenceMode[mode];
  if (!inferenceMode) throw new Error("Choose a supported inference mode.");
  // Without the Prompt API, the SDK lacks a device adapter and can choose its cloud path.
  if (inferenceMode === InferenceMode.ONLY_ON_DEVICE && !globalThis.LanguageModel) {
    throw new Error("On-device summarization is not available in this browser.");
  }
  const onDevice = inferenceMode === InferenceMode.ONLY_ON_DEVICE;
  const app = onDevice
    ? initializeApp(config, "local-device")
    : await getAttestedApp(config, siteKey, debugToken);
  const backend = !onDevice && provider === "agent-platform" ? new AgentPlatformBackend() : new GoogleAIBackend();
  const ai = getAI(app, { backend });
  const model = getGenerativeModel(ai, { mode: inferenceMode });
  if (inferenceMode === InferenceMode.ONLY_ON_DEVICE) {
    await model.initializeDeviceModel(progress);
    deviceReady?.();
  } else if (inferenceMode === InferenceMode.PREFER_ON_DEVICE) {
    // A pending download should not delay an authorized cloud fallback.
    void model.initializeDeviceModel().catch(() => {});
  }
  const { response } = await model.generateContent(prompt);
  return { source: response.inferenceSource, text: response.text() };
}
