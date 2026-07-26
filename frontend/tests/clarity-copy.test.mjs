import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = async (path) =>
  readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("marketing demos avoid unexplained investing shorthand", async () => {
  const copy = [
    await source("src/app/page.tsx"),
    await source("src/app/_mkt/thesis-demo.tsx"),
    await source("src/app/_mkt/conviction-demo.tsx"),
    await source("src/app/_mkt/timeline.tsx"),
  ].join("\n");

  for (const phrase of [
    "Story changed",
    "robotaxi optionality",
    "hyperscaler capex",
    "YoY",
    "Thesis reaffirmed",
    "Thesis invalidated",
  ]) {
    assert.doesNotMatch(copy, new RegExp(phrase, "i"), `unclear marketing phrase remains: ${phrase}`);
  }
});

test("unfamiliar product terms have nearby definitions", async () => {
  const landing = await source("src/app/page.tsx");
  const pricing = await source("src/app/(marketing)/pricing/page.tsx");

  assert.match(landing, /label="Decision record"/);
  assert.match(landing, /label="Counter-thesis"/);
  assert.match(pricing, /A 0–100 summary of how recent evidence compares/);
  assert.match(pricing, /Builds the strongest argument against owning a stock/);
  assert.match(pricing, /Returns to an earlier hold, trim or exit decision/);
});

test("info tips work with hover, keyboard focus and a tap", async () => {
  const infoTip = await source("src/components/ui/info-tip.tsx");

  assert.match(infoTip, /aria-expanded=\{open\}/);
  assert.match(infoTip, /onClick=\{\(\) => setOpen/);
  assert.match(infoTip, /onMouseEnter=\{\(\) => setOpen/);
  assert.match(infoTip, /onFocus=\{\(\) => setOpen/);
  assert.match(infoTip, /event\.key === "Escape"/);
  assert.match(infoTip, /createPortal/);
  assert.match(infoTip, /window\.innerWidth - width - gutter/);
});
