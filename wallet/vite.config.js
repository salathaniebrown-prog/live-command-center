import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/wallet/",
  plugins: [react()],
  build: {
    outDir: "../public/wallet",
    emptyOutDir: true
  }
});
