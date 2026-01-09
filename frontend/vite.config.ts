import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/pdf": "http://localhost:8000",
      "/files": "http://localhost:8000",
      "/news": "http://localhost:8000",
    },
  },
});
