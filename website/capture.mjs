import { spawn } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const captureDir = path.join(__dirname, ".captures");

await mkdir(captureDir, { recursive: true });

const server = spawn("npx", ["vite", "--host", "127.0.0.1", "--port", "4177"], {
  cwd: __dirname,
  stdio: "inherit",
});

try {
  const { chromium } = await import("playwright");
  await new Promise((resolve) => setTimeout(resolve, 1400));
  const browser = await chromium.launch();
  for (const viewport of [
    { name: "desktop", width: 1440, height: 1000 },
    { name: "mobile", width: 390, height: 920 },
  ]) {
    const page = await browser.newPage({ viewport });
    await page.goto("http://127.0.0.1:4177/", { waitUntil: "networkidle" });
    await page.screenshot({ path: path.join(captureDir, `${viewport.name}.png`), fullPage: true });
    await page.close();
  }
  await browser.close();
} finally {
  server.kill("SIGTERM");
}
