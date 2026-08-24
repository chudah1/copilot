import assert from "node:assert/strict";
import test from "node:test";

import { getApiBaseUrl } from "../src/lib/api-base.ts";

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;
const originalNodeEnv = process.env.NODE_ENV;
const env = process.env as Record<string, string | undefined>;

test.after(() => {
  if (originalApiUrl === undefined) delete env.NEXT_PUBLIC_API_URL;
  else env.NEXT_PUBLIC_API_URL = originalApiUrl;
  if (originalNodeEnv === undefined) delete env.NODE_ENV;
  else env.NODE_ENV = originalNodeEnv;
});

test("uses the production API when the public API URL is omitted", () => {
  delete env.NEXT_PUBLIC_API_URL;
  env.NODE_ENV = "production";

  assert.equal(getApiBaseUrl(), "https://api.penkeep.io");
});

test("normalises an explicitly configured API URL", () => {
  env.NEXT_PUBLIC_API_URL = "api.example.com///";

  assert.equal(getApiBaseUrl(), "https://api.example.com");
});
