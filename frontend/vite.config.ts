import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
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
