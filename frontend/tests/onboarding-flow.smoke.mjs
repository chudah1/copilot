import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const onboardingSource = await readFile(
  new URL("../src/app/onboarding/page.tsx", import.meta.url),
  "utf8",
);

test("onboarding advances through a native form submission", () => {
  assert.match(onboardingSource, /<form[\s\S]*?onSubmit=/);
  assert.match(onboardingSource, /<Button[\s\S]*?type="submit"/);
  assert.match(onboardingSource, /<button[\s\S]*?type="button"[\s\S]*?onClick=\{handleSkip\}/);
});

test("onboarding does not gate the next question behind an exit animation", () => {
  assert.doesNotMatch(onboardingSource, /AnimatePresence/);
  assert.doesNotMatch(onboardingSource, /exit=/);
});
