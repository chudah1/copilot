import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = async (path) =>
  readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("dashboard puts positions before supporting portfolio context", async () => {
  const dashboard = await source("src/app/dashboard/page.tsx");

  assert.match(dashboard, /id="positions" className="order-1/);
  assert.match(dashboard, /Portfolio snapshot/);
  assert.match(dashboard, /lg:sticky lg:top-\[96px\]/);
  assert.match(dashboard, /No earnings calls in the next three weeks/);
  assert.doesNotMatch(dashboard, /usable but not sharp/i);
});

test("position header carries holding facts and the global note action", async () => {
  const header = await source(
    "src/app/dashboard/positions/[ticker]/position-header.tsx",
  );
  const page = await source("src/app/dashboard/positions/[ticker]/page.tsx");

  assert.match(header, />\s*\+ Note\s*</);
  assert.match(header, /Shares/);
  assert.match(header, /Current price/);
  assert.match(header, /Average cost/);
  assert.match(page, /<PositionNoteDialog/);
  assert.doesNotMatch(page, /showPositionDetails/);
});

test("monitoring leads with the answer instead of internal activity counts", async () => {
  const monitoring = await source(
    "src/app/dashboard/positions/[ticker]/monitoring-tab.tsx",
  );

  assert.match(monitoring, /No new evidence needs a decision/);
  assert.match(monitoring, /part of your written case it affects/);
  assert.doesNotMatch(monitoring, /Verdicts on file/);
  assert.doesNotMatch(monitoring, /Signal map/);
});

test("long evidence and history lists are collapsed by default", async () => {
  const history = await source("src/components/thesis/conviction-log.tsx");
  const heldUp = await source(
    "src/components/monitoring/held-up-this-week.tsx",
  );
  const reviewed = await source(
    "src/components/monitoring/reviewed-this-week.tsx",
  );
  const audit = await source(
    "src/components/thesis/historical-audit-card.tsx",
  );

  assert.match(history, /filteredEntries\.slice\(0, 2\)/);
  assert.match(heldUp, /items\.slice\(0, 3\)/);
  assert.match(reviewed, /items\.slice\(0, 3\)/);
  assert.match(audit, /results\.slice\(0, 3\)/);
});

test("homepage offers the stock risk check directly", async () => {
  const landing = await source("src/app/page.tsx");
  const search = await source("src/app/_mkt/stress-test-search.tsx");
  const research = await source("src/app/research/page.tsx");

  assert.match(landing, /<StressTestSearch/);
  assert.match(search, /Free stress test — before you buy/);
  assert.match(search, /router\.push\(`\/research\/\$\{ticker\}`\)/);
  assert.match(research, /Check the case before you buy/);
});

test("portfolio weights use the same live total shown in the snapshot", async () => {
  const dashboard = await source("src/app/dashboard/page.tsx");

  assert.equal(
    dashboard.match(/totalValue=\{displayTotalValue\}/g)?.length,
    2,
    "both the position card and position peek should use the displayed live total",
  );
  assert.doesNotMatch(dashboard, /totalValue=\{summary\?\.total_value \?\? 0\}/);
});

test("digest delivery failures are not shown as failed content", async () => {
  const archive = await source("src/app/digests/page.tsx");
  const detail = await source("src/app/digests/[id]/page.tsx");

  assert.match(archive, /digestStatusLabel\(d\)/);
  assert.match(detail, /digestStatusLabel\(digest\)/);
  assert.doesNotMatch(archive, /● \{d\.status\}/);
  assert.doesNotMatch(detail, /● \{digest\.status\}/);
});

test("the price sparkline explains its period, prices and evidence markers", async () => {
  const sparkline = await source("src/components/portfolio/price-sparkline.tsx");

  assert.match(sparkline, /Price since you wrote this case/);
  assert.match(sparkline, /Evidence that tested your case/);
  assert.match(sparkline, /formatCurrency\(firstClose, data\.currency\)/);
  assert.match(sparkline, /<button/);
  assert.match(sparkline, /event\.title/);
});
