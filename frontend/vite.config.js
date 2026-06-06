import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Dev: forward API calls to the Flask backend.
      "/api": "http://localhost:5050",
    },
  },
});
