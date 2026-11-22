import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const offlineWorker = readFileSync(new URL("./offline-worker.js", import.meta.url), "utf8");

export default {
  plugins: [{
    name: "preflight-offline-shell",
    apply: "build",
    enforce: "post",
    generateBundle(_options, bundle) {
      const assets = Object.keys(bundle).filter(name => /\.(html|js|css)$/.test(name)).sort();
      const version = createHash("sha256").update(offlineWorker);
      for (const name of assets) {
        const item = bundle[name];
        version.update(name).update(item.type === "chunk" ? item.code : item.source);
      }
      const metadata = `const ASSETS = ${JSON.stringify(assets)};\nconst VERSION = ${JSON.stringify(version.digest("hex"))};\n`;
      this.emitFile({ type: "asset", fileName: "app-shell-worker.js", source: metadata + offlineWorker });
    },
  }],
  build: {
    target: "es2022",
    rollupOptions: {
      input: {
        device: fileURLToPath(new URL("./index.html", import.meta.url)),
        firebase: fileURLToPath(new URL("./firebase.html", import.meta.url)),
        notes: fileURLToPath(new URL("./notes.html", import.meta.url)),
      },
    },
  },
};
