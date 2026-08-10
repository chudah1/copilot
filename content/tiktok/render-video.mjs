import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { videos } from "./videos.mjs";
import { videoDuration } from "./video-scenes.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const outputRoot = resolve(here, "output");
const template = pathToFileURL(resolve(here, "video-template.html")).href;
const fps = 24;

const playwrightModule = process.env.PLAYWRIGHT_MODULE || "playwright";
const ffmpegPath = process.env.FFMPEG_PATH || "ffmpeg";
const { chromium } = await import(playwrightModule);

const requestedSlugs = new Set(process.argv.slice(2));
const targets = requestedSlugs.size === 0 ? videos : videos.filter((video) => requestedSlugs.has(video.slug));
if (targets.length === 0) {
  throw new Error(`No video matched: ${[...requestedSlugs].join(", ")}`);
}

mkdirSync(outputRoot, { recursive: true });

const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  args: ["--allow-file-access-from-files", "--disable-gpu"],
});

for (const video of targets) {
  const duration = videoDuration(video);
  const outputDir = resolve(outputRoot, video.slug);
  const outputVideo = resolve(outputDir, "video.mp4");
  mkdirSync(outputDir, { recursive: true });

  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  page.setDefaultTimeout(120_000);
  await page.goto(`${template}?video=${encodeURIComponent(video.slug)}`, { waitUntil: "load" });
  await page.waitForFunction(() => document.documentElement.dataset.ready === "true");

  const ffmpeg = spawn(ffmpegPath, [
    "-y",
    "-f", "image2pipe",
    "-vcodec", "mjpeg",
    "-framerate", String(fps),
    "-i", "pipe:0",
    "-an",
    "-c:v", "libx264",
    "-preset", "medium",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    outputVideo,
  ], { stdio: ["pipe", "inherit", "inherit"] });

  const waitForDrain = () => new Promise((done) => ffmpeg.stdin.once("drain", done));
  const totalFrames = Math.ceil(duration * fps);

  for (let frame = 0; frame < totalFrames; frame += 1) {
    const time = frame / fps;
    await page.evaluate((value) => window.renderAt(value), time);
    const image = await page.screenshot({ type: "jpeg", quality: 94, timeout: 120_000 });
    if (!ffmpeg.stdin.write(image)) await waitForDrain();
    if (frame % fps === 0) process.stdout.write(`${video.slug}: rendered ${Math.round(time)}s / ${duration}s\r`);
  }

  ffmpeg.stdin.end();
  const exitCode = await new Promise((done) => ffmpeg.once("close", done));
  await page.evaluate((value) => window.renderAt(value), video.coverAt ?? 1);
  await page.screenshot({ path: resolve(outputDir, "cover.png"), type: "png", timeout: 120_000 });
  await page.close();
  if (exitCode !== 0) throw new Error(`FFmpeg exited with code ${exitCode} for ${video.slug}`);

  writeFileSync(resolve(outputDir, "title.txt"), `${video.title}\n`, "utf8");
  writeFileSync(resolve(outputDir, "caption.txt"), `${video.caption}\n\n${video.hashtags.join(" ")}\n`, "utf8");
  writeFileSync(
    resolve(outputDir, "posting-notes.txt"),
    `Format: 1080 × 1920 vertical MP4\nDuration: ${duration}s\nAudio: Add a subtle Commercial Sounds track in TikTok at 5–10% volume.\nCover frame: rendered at ${video.coverAt ?? 1}s.\n`,
    "utf8",
  );

  console.log(`\nCreated ${outputVideo}`);
}

await browser.close();
