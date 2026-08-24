import assert from "node:assert/strict";
import test from "node:test";

import { resolveBackendApiUrl } from "../src/lib/server-api-url.ts";

test("uses the production API when no deployment override is configured", () => {
  assert.equal(
    resolveBackendApiUrl({ backendUrl: "", publicApiUrl: "", nodeEnv: "production" }),
    "https://api.penkeep.io",
  );
});

test("keeps local development pointed at the local backend", () => {
  assert.equal(
    resolveBackendApiUrl({ backendUrl: "", publicApiUrl: "", nodeEnv: "development" }),
    "http://localhost:8000",
  );
});

test("normalises an explicitly configured backend URL", () => {
  assert.equal(
    resolveBackendApiUrl({ backendUrl: "api.example.com///", nodeEnv: "production" }),
    "https://api.example.com",
  );
});
