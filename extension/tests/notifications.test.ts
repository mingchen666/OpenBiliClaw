import test from "node:test";
import assert from "node:assert/strict";

import {
  buildChromeNotificationOptions,
  buildNotificationId,
  parseNotificationBvid,
} from "../src/background/notifications.ts";

test("buildNotificationId and parseNotificationBvid round trip bvid", () => {
  const notificationId = buildNotificationId("BV1ROUND");

  assert.equal(notificationId, "openbiliclaw-recommendation:BV1ROUND");
  assert.equal(parseNotificationBvid(notificationId), "BV1ROUND");
  assert.equal(parseNotificationBvid("other"), "");
});

test("buildChromeNotificationOptions fills stable fallback copy", () => {
  const options = buildChromeNotificationOptions({
    recommendation_id: 1,
    bvid: "BV1TEST",
    title: "",
    reason: "",
  });

  assert.equal(options.type, "basic");
  assert.equal(options.title, "阿B 给你补到一条新内容");
  assert.equal(options.message, "这条大概率会对你的胃口。");
  assert.equal(options.iconUrl, "icons/icon128.png");
});
