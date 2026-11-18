import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // Lipwad needs no offline mode (DECISIONS: offline capture is out of scope), so the
      // service worker unregisters itself and clears its caches. Visitors with an older
      // caching worker are cleaned up and reloaded once on their next visit.
      selfDestroying: true,
      injectRegister: false,
      manifest: {
        name: "Lipwad",
        short_name: "Lipwad",
        description: "Complete, cited SHA claims from paper records and voice notes",
        theme_color: "#0A1F44",
        background_color: "#F5F3EE",
        display: "standalone",
      },
    }),
  ],
  server: {
    fs: { allow: [".."] },
    proxy: { "/api": "http://localhost:8000" },
  },
});
