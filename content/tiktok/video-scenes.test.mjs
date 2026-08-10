import { test } from "node:test";
import assert from "node:assert/strict";
import {
  esc,
  accentTitle,
  sceneVisibility,
  sceneFadeIn,
  resolveActiveScene,
  videoDuration,
  chartProgress,
  renderSceneHTML,
} from "./video-scenes.mjs";

test("esc escapes HTML-significant characters", () => {
  assert.equal(esc("Tom & Jerry <script>"), "Tom &amp; Jerry &lt;script&gt;");
});

test("esc defaults to an empty string", () => {
  assert.equal(esc(), "");
});

test("accentTitle wraps the accent substring and converts newlines to <br>", () => {
  const html = accentTitle("You made\nmoney.", "money.");
  assert.equal(html, 'You made<br><span class="accent">money.</span>');
});

test("accentTitle returns the escaped title unchanged when there is no accent", () => {
  assert.equal(accentTitle("Plain title", undefined), "Plain title");
});

test("sceneVisibility is 0 well outside the scene window and 1 mid-scene", () => {
  const scene = { start: 5, end: 8 };
  assert.equal(sceneVisibility(scene, 0), 0);
  assert.equal(sceneVisibility(scene, 6.5), 1);
});

test("sceneFadeIn rises from 0 at the scene start to 1 after the crossfade window", () => {
  const scene = { start: 5 };
  assert.equal(sceneFadeIn(scene, 5), 0);
  assert.equal(sceneFadeIn(scene, 5.38), 1);
});

test("resolveActiveScene picks the most visible scene at a given time", () => {
  const scenes = [
    { start: 0, end: 2.8, treatment: "night" },
    { start: 2.45, end: 5.4, treatment: "paper" },
    { start: 5.05, end: 8.15, treatment: "green" },
  ];
  assert.equal(resolveActiveScene(scenes, 1).treatment, "night");
  assert.equal(resolveActiveScene(scenes, 4).treatment, "paper");
  assert.equal(resolveActiveScene(scenes, 6.5).treatment, "green");
});

test("videoDuration returns the latest scene end time", () => {
  const video = { scenes: [{ end: 2.8 }, { end: 21 }, { end: 11.45 }] };
  assert.equal(videoDuration(video), 21);
});

test("chartProgress rises from 0 at the scene start to 1 after 1.6s", () => {
  const scene = { start: 5 };
  assert.equal(chartProgress(scene, 5), 0);
  assert.equal(chartProgress(scene, 6.6), 1);
});

test("renderSceneHTML builds a hook scene with eyebrow and accented multi-line title", () => {
  const html = renderSceneHTML({ type: "hook", eyebrow: "THE OUTCOME", title: "You made\nmoney.", accent: "money." });
  assert.match(html, /<div class="eyebrow">THE OUTCOME<\/div>/);
  assert.match(html, /<h1>You made<br><span class="accent">money\.<\/span><\/h1>/);
});

test("renderSceneHTML builds a statement scene with an optional body", () => {
  const withBody = renderSceneHTML({ type: "statement", eyebrow: "X", title: "Title", body: "Body text" });
  assert.match(withBody, /<h2>Title<\/h2>/);
  assert.match(withBody, /<p class="subcopy">Body text<\/p>/);

  const withoutBody = renderSceneHTML({ type: "statement", eyebrow: "X", title: "Title" });
  assert.doesNotMatch(withoutBody, /subcopy/);
});

test("renderSceneHTML builds a stat scene, with chart markup only when chart data is present", () => {
  const withChart = renderSceneHTML({ type: "stat", eyebrow: "X", stat: "+42%", body: "Body", chart: { path: "M0,0" } });
  assert.match(withChart, /<div class="money">\+42%<\/div>/);
  assert.match(withChart, /<path d="M0,0" \/>/);

  const withoutChart = renderSceneHTML({ type: "stat", eyebrow: "X", stat: "+42%", body: "Body" });
  assert.doesNotMatch(withoutChart, /<svg/);
});

test("renderSceneHTML builds a compare scene with two cards", () => {
  const html = renderSceneHTML({
    type: "compare",
    eyebrow: "X",
    title: "A win can mean two different things.",
    compare: {
      left: { label: "THE OUTCOME", copy: "Luck was rewarded." },
      right: { label: "THE PROCESS", copy: "The reasoning was sound." },
    },
  });
  assert.match(html, /THE OUTCOME/);
  assert.match(html, /Luck was rewarded\./);
  assert.match(html, /THE PROCESS/);
  assert.match(html, /The reasoning was sound\./);
});

test("renderSceneHTML builds a quote scene", () => {
  const html = renderSceneHTML({ type: "quote", eyebrow: "X", quote: "Would I make the same choice?" });
  assert.match(html, /<div class="question">Would I make the same choice\?<\/div>/);
});

test("renderSceneHTML builds a closing scene with the BH mark and accented title", () => {
  const html = renderSceneHTML({
    type: "closing",
    title: "Judge the process\nbefore the outcome.",
    accent: "before the outcome.",
    body: "Follow Before Hindsight for clearer investment decisions.",
  });
  assert.match(html, /<div class="closing-mark">BH<\/div>/);
  assert.match(html, /<span class="accent">before the outcome\.<\/span>/);
});

test("renderSceneHTML throws on an unknown scene type", () => {
  assert.throws(() => renderSceneHTML({ type: "mystery" }), /Unknown scene type/);
});
