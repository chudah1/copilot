import { test } from "node:test";
import assert from "node:assert/strict";
import { videos } from "./videos.mjs";
import { videoDuration, renderSceneHTML } from "./video-scenes.mjs";

test("every video has a non-empty slug, title, caption, hashtags, and scenes", () => {
  for (const video of videos) {
    assert.ok(video.slug, "missing slug");
    assert.ok(video.title, "missing title");
    assert.ok(video.caption, "missing caption");
    assert.ok(Array.isArray(video.hashtags) && video.hashtags.length > 0, `${video.slug}: missing hashtags`);
    assert.ok(Array.isArray(video.scenes) && video.scenes.length > 0, `${video.slug}: missing scenes`);
  }
});

test("scenes are ordered by start time and never end before they start", () => {
  for (const video of videos) {
    let previousStart = -Infinity;
    for (const scene of video.scenes) {
      assert.ok(scene.end > scene.start, `${video.slug}: a scene ends before it starts`);
      assert.ok(scene.start >= previousStart, `${video.slug}: scenes are out of start-time order`);
      previousStart = scene.start;
    }
  }
});

test("video-01, migrated from the one-off script, has 7 scenes and ends at 21s", () => {
  const video = videos.find((entry) => entry.slug === "video-01-profitable-bad-decision");
  assert.ok(video, "video-01 is missing from videos.mjs");
  assert.equal(video.scenes.length, 7);
  assert.equal(videoDuration(video), 21);
});

test("every scene has a valid treatment and renders non-empty HTML", () => {
  const validTreatments = ["night", "paper", "green"];
  for (const video of videos) {
    for (const scene of video.scenes) {
      assert.ok(validTreatments.includes(scene.treatment), `${video.slug}: invalid treatment "${scene.treatment}"`);
      const html = renderSceneHTML(scene);
      assert.ok(typeof html === "string" && html.length > 0, `${video.slug}: renderSceneHTML produced empty output`);
    }
  }
});
