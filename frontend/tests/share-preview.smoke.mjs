import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";

const baseUrl = process.env.PENKEEP_PREVIEW_URL ?? "http://127.0.0.1:3000";
const vercelFaviconSha256 = "2b8ad2d33455a8f736fc3a8ebf8f0bdea8848ad4c0db48a2833bd0f9cd775932";

function metadataTag(html, attribute, value) {
  const escapedValue = value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return html.match(new RegExp(`<meta[^>]+${attribute}="${escapedValue}"[^>]*>`, "i"))?.[0] ?? null;
}

function contentFromTag(tag) {
  return tag?.match(/content="([^"]+)"/i)?.[1] ?? null;
}

test("shared links expose PenKeep branding to preview crawlers", async () => {
  const response = await fetch(baseUrl, {
    headers: { "user-agent": "Slackbot-LinkExpanding 1.0" },
  });
  assert.equal(response.status, 200);
  const html = await response.text();

  const openGraphImageTag = metadataTag(html, "property", "og:image");
  const twitterImageTag = metadataTag(html, "name", "twitter:image");

  assert.ok(metadataTag(html, "property", "og:title"), "missing og:title");
  assert.ok(openGraphImageTag, "missing og:image");
  assert.ok(metadataTag(html, "name", "twitter:card"), "missing twitter:card");
  assert.ok(twitterImageTag, "missing twitter:image");

  for (const imageUrl of [contentFromTag(openGraphImageTag), contentFromTag(twitterImageTag)]) {
    assert.ok(imageUrl, "share image tag has no URL");
    const declaredImageUrl = new URL(imageUrl, baseUrl);
    const imageResponse = await fetch(
      new URL(`${declaredImageUrl.pathname}${declaredImageUrl.search}`, baseUrl),
    );
    assert.equal(imageResponse.status, 200);
    assert.match(imageResponse.headers.get("content-type") ?? "", /^image\/png/);
  }

  const faviconPath = html.match(/<link[^>]+rel="icon"[^>]+href="([^"]*favicon\.ico[^"]*)"/i)?.[1];
  assert.ok(faviconPath, "missing favicon.ico");
  const faviconResponse = await fetch(new URL(faviconPath, baseUrl));
  assert.equal(faviconResponse.status, 200);
  const faviconHash = createHash("sha256")
    .update(Buffer.from(await faviconResponse.arrayBuffer()))
    .digest("hex");
  assert.notEqual(faviconHash, vercelFaviconSha256, "favicon is still the Vercel triangle");
});
