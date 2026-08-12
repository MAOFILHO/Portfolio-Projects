import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/health": "http://localhost:8000",
      "/scenarios": "http://localhost:8000",
      "/dataset": "http://localhost:8000",
      "/finetune": "http://localhost:8000",
      "/deploy": "http://localhost:8000",
      "/infer": "http://localhost:8000",
      "/auth": "http://localhost:8000",
      "/cost": "http://localhost:8000",
    },
  },
});
