import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = async (path) =>
  readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("position changes use the guided review without duplicating the old summary", async () => {
  const monitoring = await source(
    "src/app/dashboard/positions/[ticker]/monitoring-tab.tsx",
  );
  const checkIn = await source("src/components/thesis/thesis-check-in.tsx");

  assert.match(monitoring, /presentation="guided"/);
  assert.match(monitoring, /key=\{thesisId\}/);
  assert.match(monitoring, /const noDecisionPending = pendingDecisionCount === 0/);
  assert.match(monitoring, /pendingDecisionCount > 0 && thesisId/);
  assert.match(monitoring, /noDecisionPending && reviewedItems\.length > 0/);
  assert.match(checkIn, /What needs you/);
  assert.match(checkIn, /Review evidence/);
  assert.match(checkIn, /Make the call/);
  assert.match(checkIn, /Save decision/);
  assert.match(checkIn, /const guidedReviewActive = guided && pendingClaims\.length > 0/);
  assert.match(checkIn, /Decision saved but follow-up refresh failed/);
});

test("position navigation exposes one clear section row", async () => {
  const page = await source("src/app/dashboard/positions/[ticker]/page.tsx");
  const header = await source(
    "src/app/dashboard/positions/[ticker]/position-header.tsx",
  );

  assert.match(header, /"reason" \| "changes" \| "checks" \| "history"/);
  assert.match(page, /label: "Reason"/);
  assert.match(page, /label: "Changes"/);
  assert.match(page, /label: "Checks"/);
  assert.match(page, /label: "History"/);
  assert.doesNotMatch(page, /layoutId="thesis-sub-indicator"/);
  assert.match(page, /Keep browser back\/forward navigation aligned/);
  assert.match(page, /pulse\.unresolved_event_count/);
  assert.doesNotMatch(page, /events\.filter\(\(e\) => !e\.review_action\)\.length/);
  assert.match(page, /mutateSWR\("\/api\/portfolio\/pulse", portfolioPulse/);
  assert.match(page, /holding \? refreshPulse\(holding\.id\) : Promise\.resolve\(\)/);
});
