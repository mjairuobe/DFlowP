import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Testkonfiguration: API-Key für Login/Cookie bündelt Vite als VITE_DFLOWP_API_KEY (siehe src/authProvider, src/dflowpApiKeyCookie).

export default defineConfig({
  plugins: [react()],
});
