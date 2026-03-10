import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

test("popup header keeps compact status inline with brand row", () => {
  const popupHtml = readFileSync(resolve("popup", "popup.html"), "utf8");
  const heroTopBlock = popupHtml.match(/\.hero-top\s*\{[^}]+\}/)?.[0] ?? "";
  const statusBadgeBlock = popupHtml.match(/\.status-badge\s*\{[^}]+\}/)?.[0] ?? "";
  const popupMarkup = popupHtml.match(/<header class="hero">[\s\S]*?<\/header>/)?.[0] ?? "";

  assert.match(heroTopBlock, /grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto;/);
  assert.match(statusBadgeBlock, /padding:\s*6px\s+10px;/);
  assert.doesNotMatch(popupMarkup, /id="statusText"/);
});
