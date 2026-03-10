import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

test("chat tab layout keeps chat shell and message list from collapsing", () => {
  const popupHtml = readFileSync(resolve("popup", "popup.html"), "utf8");

  assert.match(popupHtml, /\.chat-shell\s*\{[\s\S]*?flex-shrink:\s*0;/);
  assert.match(popupHtml, /\.chat-messages\s*\{[\s\S]*?min-height:\s*72px;/);
});
