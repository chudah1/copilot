import test from "node:test";
import assert from "node:assert/strict";

import { describeWatchHint } from "../src/lib/watch-hints.ts";

test("describeWatchHint explains proxy metric watches honestly when threshold is implicit", () => {
  const text = describeWatchHint({
    kind: "metric_threshold",
    metric: "revenue_growth_yoy",
    operator: ">=",
    threshold: 0,
    proxy_for: "HIMS compounded GLP-1 and DTC prescription revenue growth",
  });

  assert.equal(
    text,
    "Track revenue growth as a proxy for HIMS compounded GLP-1 and DTC prescription revenue growth.",
  );
});

test("describeWatchHint keeps explicit threshold while disclosing the proxy", () => {
  const text = describeWatchHint({
    kind: "metric_threshold",
    metric: "revenue_growth_yoy",
    operator: ">=",
    threshold: 0.15,
    proxy_for: "SHOP gross merchandise volume growth",
  });

  assert.equal(
    text,
    "Review if Revenue growth falls below 15%, using it as a proxy for SHOP gross merchandise volume growth.",
  );
});
