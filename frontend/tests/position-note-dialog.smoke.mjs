import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const dialogSource = await readFile(
  new URL("../src/app/dashboard/positions/[ticker]/position-note-dialog.tsx", import.meta.url),
  "utf8",
);

test("position note dialog preserves spacing when its shell uses p-0", () => {
  assert.match(
    dialogSource,
    /<DialogHeader className="[^"]*\bpx-5\b[^"]*\bpt-5\b[^"]*"/,
  );
  assert.match(
    dialogSource,
    /<DialogFooter className="[^"]*\bmx-0\b[^"]*\bmb-0\b[^"]*"/,
  );
});

test("position note field has a stable accessible name", () => {
  assert.match(dialogSource, /<textarea[\s\S]*?aria-label="Position note"/);
});
