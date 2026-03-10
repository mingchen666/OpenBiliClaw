export const NOTIFICATION_PREFIX = "openbiliclaw-recommendation:";

export type PendingNotification = {
  recommendation_id: number;
  bvid: string;
  title: string;
  reason: string;
};

export function buildNotificationId(bvid: string): string {
  return `${NOTIFICATION_PREFIX}${bvid}`;
}

export function parseNotificationBvid(notificationId: string): string {
  if (!notificationId.startsWith(NOTIFICATION_PREFIX)) {
    return "";
  }
  return notificationId.slice(NOTIFICATION_PREFIX.length);
}

export function buildChromeNotificationOptions(
  item: PendingNotification,
): chrome.notifications.NotificationCreateOptions {
  return {
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: item.title || "阿B 给你补到一条新内容",
    message: item.reason || "这条大概率会对你的胃口。",
    priority: 2,
  };
}
