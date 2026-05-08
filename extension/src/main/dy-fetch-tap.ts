/**
 * Douyin MAIN-world fetch-tap.
 *
 * Pattern: install a wrapper around `window.fetch` (and
 * `XMLHttpRequest.prototype.send`) that **observes** the response
 * bodies of `/aweme/v1/web/aweme/{post,favorite,like}/` and
 * `/aweme/v1/web/user/follow/list/` calls and posts captured items
 * back to the content script via `window.postMessage`. Douyin's own
 * `webmssdk.js` has already signed the outgoing call before our
 * wrapper sees it, so we never compute X-Bogus / msToken / `_signature`
 * ourselves.
 *
 * **Critical timing detail** (verified empirically 2026-05-07 via
 * chrome-devtools MCP probe — see
 * docs/plans/2026-05-06-douyin-bootstrap-import-design.md §3 step 5):
 * Douyin's page bundle wraps `window.fetch` with its own axios-style
 * wrapper *after* document_start. Installing at `runAt:"document_start"`
 * is shadowed by the page bundle's later wrapper and captures **zero**
 * responses. The bootstrap content script must
 * `await waitForDouyinSdk(window, 8000)` (polling for
 * `window.byted_acrawler`) before calling `installFetchTap`.
 * Wrapping the SDK's wrapper preserves the signing (their wrapper
 * signs internally) and adds our observation as the outermost layer.
 *
 * This module does NOT auto-install. Side effects only happen when
 * the content script explicitly calls `installFetchTap(window, ...)`.
 */

export type DouyinScope = "dy_post" | "dy_collect" | "dy_like" | "dy_follow";

export interface DouyinBootstrapItem {
  scope: DouyinScope;
  aweme_id: string;
  creator_sec_uid: string;
  url: string;
  title: string;
  author: string;
  author_sec_uid: string;
  cover_url: string;
}

/**
 * Map a Douyin API URL to a bootstrap scope, or null if the endpoint
 * is not one we care about. Used by both the fetch-tap to decide
 * whether to capture and by the executor to route incoming
 * postMessage events.
 *
 * Endpoint catalog cross-referenced with Johnserf-Seed/f2 (Apache-2.0,
 * read-only reference — see design doc §"Open-Source Prior Art").
 * Empirically validated against real /jingxuan landing-page traffic.
 */
export function classifyDouyinResponseUrl(url: string): DouyinScope | null {
  if (!url) return null;
  // Strip query string before matching so request_source params don't
  // disturb the path-based decision.
  const path = url.split("?", 1)[0] ?? "";
  if (path.includes("/aweme/v1/web/aweme/post/")) return "dy_post";
  if (path.includes("/aweme/v1/web/aweme/favorite/")) return "dy_collect";
  if (path.includes("/aweme/v1/web/aweme/collection/")) return "dy_collect";
  if (path.includes("/aweme/v1/web/aweme/like/")) return "dy_like";
  if (path.includes("/aweme/v1/web/user/follow/list/")) return "dy_follow";
  if (path.includes("/aweme/v1/web/user/following/list/")) return "dy_follow";
  return null;
}

function pickString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function pickFirstUrl(coverField: unknown): string {
  if (!coverField || typeof coverField !== "object") return "";
  const cover = coverField as { url_list?: unknown };
  if (!Array.isArray(cover.url_list)) return "";
  const first = cover.url_list.find((u) => typeof u === "string" && u);
  return typeof first === "string" ? first : "";
}

function pickAuthor(awemeAuthor: unknown): { nickname: string; sec_uid: string } {
  if (!awemeAuthor || typeof awemeAuthor !== "object") return { nickname: "", sec_uid: "" };
  const a = awemeAuthor as { nickname?: unknown; sec_uid?: unknown };
  return {
    nickname: pickString(a.nickname),
    sec_uid: pickString(a.sec_uid),
  };
}

/**
 * Parse a `/aweme/v1/web/aweme/{post,favorite,like}/` response into
 * normalized items. Tolerates missing `aweme_list`, wrong types,
 * and individual-row malformations (drops the bad row, keeps the rest).
 *
 * Field shape reference:
 * - `aweme_id`: stable id, used as identity key
 * - `desc` / `preview_title`: title (real /aweme/v2/web/module/feed/
 *   samples shipped preview_title alongside a blank desc — accept both)
 * - `author.nickname` / `author.sec_uid`: creator
 * - `video.cover.url_list[]`: cover image candidates
 */
export function parseAwemeListResponse(
  json: unknown,
  scope: DouyinScope,
): DouyinBootstrapItem[] {
  if (!json || typeof json !== "object") return [];
  const root = json as { aweme_list?: unknown };
  if (!Array.isArray(root.aweme_list)) return [];

  const items: DouyinBootstrapItem[] = [];
  for (const raw of root.aweme_list) {
    if (!raw || typeof raw !== "object") continue;
    const aweme = raw as {
      aweme_id?: unknown;
      desc?: unknown;
      preview_title?: unknown;
      author?: unknown;
      video?: { cover?: unknown };
    };
    const awemeId = pickString(aweme.aweme_id);
    const title = pickString(aweme.desc) || pickString(aweme.preview_title);
    if (!awemeId && !title) continue;
    const author = pickAuthor(aweme.author);
    const coverUrl = pickFirstUrl(aweme.video?.cover);
    items.push({
      scope,
      aweme_id: awemeId,
      creator_sec_uid: "",
      url: awemeId ? `https://www.douyin.com/video/${awemeId}` : "",
      title,
      author: author.nickname,
      author_sec_uid: author.sec_uid,
      cover_url: coverUrl,
    });
  }
  return items;
}

/**
 * Parse a `/aweme/v1/web/user/follow/list/` response into normalized
 * items. Accepts both `followings` and `follow_list` as the array key
 * since f2 references show the variant has shifted historically.
 */
export function parseUserFollowListResponse(json: unknown): DouyinBootstrapItem[] {
  if (!json || typeof json !== "object") return [];
  const root = json as { followings?: unknown; follow_list?: unknown };
  const list = Array.isArray(root.followings)
    ? root.followings
    : Array.isArray(root.follow_list)
      ? root.follow_list
      : null;
  if (!list) return [];

  const items: DouyinBootstrapItem[] = [];
  for (const raw of list) {
    if (!raw || typeof raw !== "object") continue;
    const creator = raw as {
      sec_uid?: unknown;
      nickname?: unknown;
      avatar_thumb?: unknown;
    };
    const secUid = pickString(creator.sec_uid);
    if (!secUid) continue;
    const nickname = pickString(creator.nickname);
    const avatarUrl = pickFirstUrl(creator.avatar_thumb);
    items.push({
      scope: "dy_follow",
      aweme_id: "",
      creator_sec_uid: secUid,
      url: `https://www.douyin.com/user/${secUid}`,
      title: nickname,
      author: nickname,
      author_sec_uid: secUid,
      cover_url: avatarUrl,
    });
  }
  return items;
}

/**
 * Poll `target.byted_acrawler` until it appears or the timeout elapses.
 * Resolves true on appearance, false on timeout. The 50ms poll
 * cadence is fine: the SDK is loaded by a synchronous script tag
 * relatively early, and a real installer typically waits 200-1500ms
 * before resolving.
 */
export async function waitForDouyinSdk(
  target: Window,
  timeoutMs: number,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  // Cast through unknown to touch the SDK-bearing field on Window.
  const t = target as unknown as { byted_acrawler?: unknown };
  while (Date.now() < deadline) {
    if (t.byted_acrawler) return true;
    await new Promise((r) => setTimeout(r, 50));
  }
  return Boolean(t.byted_acrawler);
}

type FetchLike = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

// TEMP DIAGNOSTIC (2026-05-08): post every observed /aweme*/ URL back
// so we can see what Douyin actually fetches. Rate-limited to avoid
// flooding the daemon log relay.
const URL_PROBE_TYPE = "OPENBILICLAW_DOUYIN_URL_PROBE";
const SEC_UID_DETECTED_TYPE = "OPENBILICLAW_DOUYIN_SEC_UID";
let _probeCount = 0;
let _detectedSecUid = "";
function probeUrl(transport: "fetch" | "xhr", url: string): void {
  if (!url) return;
  if (!url.includes("/aweme") && !url.includes("/user/")) return;
  if (_probeCount < 60) {
    _probeCount += 1;
    try {
      window.postMessage(
        { type: URL_PROBE_TYPE, transport, url, classified: classifyDouyinResponseUrl(url) },
        window.location.origin,
      );
    } catch {
      // best effort
    }
  }
  // Whenever we see a sec_user_id in the URL, broadcast it. The
  // isolated-world content script needs sec_uid to drive the
  // API-driven scope harvester; we can't get it from /user/self
  // (Douyin doesn't redirect that to the canonical sec_uid path).
  const m = url.match(/[?&]sec_user_id=(MS4w[\w-]+)/);
  if (m && m[1] && m[1] !== _detectedSecUid) {
    _detectedSecUid = m[1];
    try {
      window.postMessage(
        { type: SEC_UID_DETECTED_TYPE, secUid: m[1] },
        window.location.origin,
      );
    } catch {
      // best effort
    }
  }
}

/**
 * Install the fetch-tap onto `target.fetch`. Wraps whatever
 * `target.fetch` is at install time, which in production is the
 * SDK's already-installed wrapper (see waitForDouyinSdk above).
 *
 * The callback runs on every captured response. The fetch-tap never
 * mutates the original Response — we use `Response.clone()` so the
 * page's own consumer reads the body untouched.
 *
 * Returns a disposer that restores the original `target.fetch`.
 */
export function installFetchTap(
  target: Window,
  postBack: (items: DouyinBootstrapItem[], scope: DouyinScope) => void,
): () => void {
  const w = target as unknown as { fetch: FetchLike };
  const originalFetch = w.fetch;

  const wrapped: FetchLike = async (input, init) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : (input as Request).url;
    probeUrl("fetch", url);
    const resp = await originalFetch(input, init);
    const scope = classifyDouyinResponseUrl(url);
    if (scope) {
      try {
        const json: unknown = await resp.clone().json();
        const items =
          scope === "dy_follow"
            ? parseUserFollowListResponse(json)
            : parseAwemeListResponse(json, scope);
        if (items.length > 0) {
          postBack(items, scope);
        }
      } catch {
        // Body wasn't JSON or already consumed — silent skip is the
        // right move; we never want to throw inside fetch-tap because
        // the page's React app would observe the rejection.
      }
    }
    return resp;
  };

  w.fetch = wrapped;
  return (): void => {
    w.fetch = originalFetch;
  };
}

/**
 * Install an XHR tap parallel to the fetch tap. Douyin's older code
 * paths (and some user-tab endpoints) use XMLHttpRequest, which the
 * fetch wrap can't see. We hook .open() to capture the URL, then
 * listen on the per-request readystatechange (state=4) and parse
 * .responseText.
 *
 * Diagnostic-only: returns the disposer that un-wraps both .open and
 * .send.
 */
export function installXhrTap(
  target: Window,
  postBack: (items: DouyinBootstrapItem[], scope: DouyinScope) => void,
): () => void {
  const proto = (target as unknown as { XMLHttpRequest: { prototype: XMLHttpRequest } })
    .XMLHttpRequest.prototype;
  type OpenLike = (
    method: string,
    url: string | URL,
    async?: boolean,
    user?: string | null,
    password?: string | null,
  ) => void;
  const originalOpen = proto.open as unknown as OpenLike;

  const wrappedOpen: OpenLike = function wrappedOpen(
    this: XMLHttpRequest,
    method: string,
    url: string | URL,
    async?: boolean,
    user?: string | null,
    password?: string | null,
  ) {
    const urlString = typeof url === "string" ? url : url.toString();
    (this as unknown as { __obcUrl?: string }).__obcUrl = urlString;
    probeUrl("xhr", urlString);
    this.addEventListener("readystatechange", () => {
      if (this.readyState !== 4) return;
      const u = (this as unknown as { __obcUrl?: string }).__obcUrl ?? urlString;
      const scope = classifyDouyinResponseUrl(u);
      if (!scope) return;
      try {
        const text = this.responseText;
        if (!text) return;
        const json: unknown = JSON.parse(text);
        const items =
          scope === "dy_follow"
            ? parseUserFollowListResponse(json)
            : parseAwemeListResponse(json, scope);
        if (items.length > 0) postBack(items, scope);
      } catch {
        // Best-effort: never throw inside XHR listener.
      }
    });
    return originalOpen.call(this, method, url, async ?? true, user, password);
  };

  (proto as unknown as { open: OpenLike }).open = wrappedOpen;
  return (): void => {
    (proto as unknown as { open: OpenLike }).open = originalOpen;
  };
}

// ---------------------------------------------------------------------------
// Auto-install when loaded as a content_scripts MAIN-world script
// ---------------------------------------------------------------------------
//
// Side-effect block guarded by ``typeof window !== "undefined"`` so
// node:test importing the module for pure-helper tests doesn't trigger
// any real installation. Mirrors the xhs-state-bridge.ts pattern.

const FETCH_TAP_MESSAGE_TYPE = "OPENBILICLAW_DOUYIN_AWEME_PAGE";
// Install-status sentinel: MAIN world emits one of these on install
// resolve so the isolated-world content script can tell whether the
// fetch-tap successfully wrapped page-bundle fetch (status="installed")
// or whether SDK detection timed out (status="skipped_no_sdk"). Used
// for diagnosing scope_status=empty results — without this we can't
// tell "captured 0 because SDK never loaded" from "captured 0 because
// risk-control empty-200'd everything".
const FETCH_TAP_INSTALL_TYPE = "OPENBILICLAW_DOUYIN_FETCH_TAP_INSTALL";

/**
 * Replay an install-status ping a few times, spaced apart, so an
 * isolated-world content script that registered its listener slightly
 * after MAIN-world install resolved still catches one. Defensive
 * against the race we observed in the 2026-05-08 e2e probe.
 *
 * Three pings × 500ms apart covers:
 *   - content script at document_start (catches first ping at T+0)
 *   - content script at document_idle (catches third ping at T+1000ms)
 *   - any unexpected delay short of 1.5s
 */
function replayInstallStatusPing(status: "installed" | "skipped_no_sdk"): void {
  const fire = (): void => {
    window.postMessage({ type: FETCH_TAP_INSTALL_TYPE, status }, window.location.origin);
  };
  fire();
  setTimeout(fire, 500);
  setTimeout(fire, 1_000);
}

// ---------------------------------------------------------------------------
// API-driven harvester — Douyin user-tab endpoints, cursor pagination
// ---------------------------------------------------------------------------
//
// Replaces UI-scrolling for scope harvest. The MAIN-world fetch is
// already wrapped by webmssdk.js (waitForDouyinSdk above), so calls
// to window.fetch get X-Bogus / a_bogus / msToken auto-signed.
//
// Endpoints + cursor key per F2 (Apache-2.0 reference):
//   dy_post:    /aweme/v1/web/aweme/post/      max_cursor / has_more
//   dy_collect: /aweme/v1/web/aweme/favorite/  max_cursor / has_more
//   dy_like:    /aweme/v1/web/aweme/like/      max_cursor / has_more
//   dy_follow:  /aweme/v1/web/user/follow/list/  max_time / has_more
//
// Isolated-world content script invokes this via postMessage:
//   request:  { type: "OPENBILICLAW_DOUYIN_API_REQUEST",
//               requestId, scope, secUid, maxItems }
//   response: { type: "OPENBILICLAW_DOUYIN_API_RESPONSE",
//               requestId, items, error?, pages_fetched }

const API_REQUEST_TYPE = "OPENBILICLAW_DOUYIN_API_REQUEST";
const API_RESPONSE_TYPE = "OPENBILICLAW_DOUYIN_API_RESPONSE";

const SCOPE_ENDPOINT: Record<DouyinScope, string> = {
  dy_post: "/aweme/v1/web/aweme/post/",
  dy_collect: "/aweme/v1/web/aweme/favorite/",
  dy_like: "/aweme/v1/web/aweme/like/",
  dy_follow: "/aweme/v1/web/user/follow/list/",
};

function buildScopeApiUrl(
  scope: DouyinScope,
  secUid: string,
  cursor: number,
): string {
  const params = new URLSearchParams({
    device_platform: "webapp",
    aid: "6383",
    channel: "channel_pc_web",
    pc_client_type: "1",
    sec_user_id: secUid,
    count: scope === "dy_follow" ? "20" : "18",
    publish_video_strategy_type: "2",
    update_version_code: "170400",
    version_code: "170400",
    version_name: "17.4.0",
    cookie_enabled: "true",
  });
  if (scope === "dy_follow") {
    params.set("max_time", String(cursor));
    params.set("min_time", "0");
    params.set("with_fstatus", "1");
    params.set("source_type", "1");
  } else {
    params.set("max_cursor", String(cursor));
    params.set("min_cursor", "0");
    params.set("whale_cut_token", "");
    params.set("cut_version", "1");
  }
  return `${SCOPE_ENDPOINT[scope]}?${params.toString()}`;
}

interface ScopeApiResult {
  items: DouyinBootstrapItem[];
  pages_fetched: number;
}

async function harvestScopeViaApi(
  target: Window,
  scope: DouyinScope,
  secUid: string,
  maxItems: number,
): Promise<ScopeApiResult> {
  const w = target as unknown as { fetch: FetchLike };
  const items: DouyinBootstrapItem[] = [];
  const seen = new Set<string>();
  let cursor = 0;
  let pages = 0;
  const cap = Math.max(0, Math.floor(maxItems));
  const MAX_PAGES = 50; // safety
  for (let page = 0; page < MAX_PAGES && items.length < cap; page += 1) {
    const url = buildScopeApiUrl(scope, secUid, cursor);
    let json: unknown;
    try {
      const resp = await w.fetch(url, { credentials: "include" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      json = (await resp.json()) as unknown;
    } catch (err) {
      if (page === 0) throw err;
      break;
    }
    pages += 1;
    const batch =
      scope === "dy_follow"
        ? parseUserFollowListResponse(json)
        : parseAwemeListResponse(json, scope);
    for (const item of batch) {
      const key = scope === "dy_follow" ? item.creator_sec_uid : item.aweme_id;
      if (!key || seen.has(key)) continue;
      seen.add(key);
      items.push(item);
      if (items.length >= cap) break;
    }
    const root = json as Record<string, unknown>;
    const hasMore = Boolean(root.has_more);
    if (!hasMore) break;
    const nextCursor =
      scope === "dy_follow"
        ? (typeof root.min_time === "number" ? root.min_time : 0)
        : (typeof root.max_cursor === "number" ? root.max_cursor : 0);
    if (!nextCursor || nextCursor === cursor) break;
    cursor = nextCursor;
    await new Promise((r) => setTimeout(r, 300));
  }
  return { items, pages_fetched: pages };
}

function installApiHarvester(target: Window): void {
  target.addEventListener("message", (event: MessageEvent) => {
    const data = (event?.data ?? null) as Record<string, unknown> | null;
    if (!data || typeof data !== "object") return;
    if (data.type !== API_REQUEST_TYPE) return;
    const requestId = String(data.requestId ?? "");
    const scope = data.scope as DouyinScope;
    const secUid = String(data.secUid ?? "");
    const maxItems = Number(data.maxItems ?? 0);
    if (!requestId || !scope || !secUid) return;
    void (async () => {
      try {
        const result = await harvestScopeViaApi(target, scope, secUid, maxItems);
        target.postMessage(
          {
            type: API_RESPONSE_TYPE,
            requestId,
            items: result.items,
            pages_fetched: result.pages_fetched,
          },
          target.location.origin,
        );
      } catch (err) {
        target.postMessage(
          {
            type: API_RESPONSE_TYPE,
            requestId,
            items: [],
            pages_fetched: 0,
            error: String(err instanceof Error ? err.message : err),
          },
          target.location.origin,
        );
      }
    })();
  });
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  // Generous timeout: real e2e probe (2026-05-08) showed
  // skipped_no_sdk on slow page-bundle loads even when the user was
  // logged in. Bumped 8s → 15s so first navs after a chrome.tabs.create
  // have headroom; subsequent SPA-route reloads in the same tab usually
  // resolve in <500ms.
  void waitForDouyinSdk(window, 15_000).then((ready) => {
    if (!ready) {
      replayInstallStatusPing("skipped_no_sdk");
      // eslint-disable-next-line no-console
      console.debug("[OpenBiliClaw] dy fetch-tap skipped: SDK not detected");
      return;
    }
    const postItems = (items: DouyinBootstrapItem[], scope: DouyinScope): void => {
      window.postMessage(
        { type: FETCH_TAP_MESSAGE_TYPE, scope, items },
        window.location.origin,
      );
    };
    installFetchTap(window, postItems);
    installXhrTap(window, postItems);
    installApiHarvester(window);
    replayInstallStatusPing("installed");
    // eslint-disable-next-line no-console
    console.debug("[OpenBiliClaw] dy fetch-tap + API harvester installed (MAIN world)");
  });
}
