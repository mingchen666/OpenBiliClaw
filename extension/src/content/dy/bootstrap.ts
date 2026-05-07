/**
 * Douyin RENDER_DATA reader — pure, no side effects on import.
 *
 * Task 4 of the Douyin bootstrap import plan
 * (docs/plans/2026-05-06-douyin-bootstrap-import.md).
 *
 * Douyin SSR-injects a `<script id="RENDER_DATA">` element whose
 * textContent is URL-encoded JSON. Top-level key is `app`. The
 * logged-in user's sec_uid lives at one of a few canonical paths
 * inside that tree; we try each in order and return the first hit.
 *
 * Verified empirically via chrome-devtools MCP probe 2026-05-07
 * (anonymous /jingxuan landing page returned a 181 KB payload with
 * top key `app`). The exact sub-path varies between login states
 * and Douyin React-app versions, so we accept multiple shapes.
 */

/**
 * Decode a URL-encoded JSON string into its parsed value.
 * Returns null if either decoding or parsing fails — the caller is
 * expected to treat that as "RENDER_DATA missing or malformed",
 * which is recoverable (we just skip the bootstrap).
 */
export function decodeRenderData(raw: string): unknown {
  if (!raw) return null;
  let decoded: string;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    return null;
  }
  try {
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

function getNestedString(state: unknown, path: string[]): string {
  let cursor: unknown = state;
  for (const key of path) {
    if (!cursor || typeof cursor !== "object") return "";
    cursor = (cursor as Record<string, unknown>)[key];
  }
  return typeof cursor === "string" ? cursor : "";
}

function getNestedBool(state: unknown, path: string[]): boolean | null {
  let cursor: unknown = state;
  for (const key of path) {
    if (!cursor || typeof cursor !== "object") return null;
    cursor = (cursor as Record<string, unknown>)[key];
  }
  return typeof cursor === "boolean" ? cursor : null;
}

/**
 * Find the logged-in user's sec_uid by trying each canonical path
 * in priority order. Returns "" if no path resolves to a string.
 *
 * Paths are intentionally narrow — we never treat a random string
 * field as sec_uid. If Douyin reorganizes the state shape we'd
 * rather return "" (and let the executor fall back to /user/self
 * for navigation) than confidently return the wrong value.
 */
export function extractDouyinSecUidFromState(state: unknown): string {
  const candidatePaths: string[][] = [
    ["app", "user", "userInfo", "secUid"],
    ["app", "user", "userInfo", "sec_uid"],
    ["app", "userStore", "user", "secUid"],
    ["app", "userStore", "user", "sec_uid"],
    ["app", "user", "secUid"],
    ["app", "user", "sec_uid"],
  ];
  for (const path of candidatePaths) {
    const found = getNestedString(state, path);
    if (found) return found;
  }
  return "";
}

/**
 * Detect whether Douyin's RENDER_DATA represents a logged-in user.
 * Conservative: we require either an explicit `isLogin: true` field
 * OR a non-empty sec_uid. We never default to true on missing data.
 *
 * Why conservative? If we hallucinate a logged-in state and run a
 * bootstrap that hits favorite/like endpoints, we'll just get empty
 * 200s and silently store nothing — but the user's daemon will
 * believe Douyin had no signals to give, which corrupts the source
 * mix calculation. Better to skip the bootstrap entirely.
 */
export function extractDouyinLoginState(state: unknown): boolean {
  const explicitLogin = getNestedBool(state, ["app", "user", "userInfo", "isLogin"]);
  if (explicitLogin === true) return true;
  if (explicitLogin === false) return false;
  // Fall back to "do we have a sec_uid" as a secondary positive
  // signal. Only positive — empty sec_uid does NOT prove logged-out
  // because some Douyin states publish sec_uid lazily. But we still
  // need something to anchor on, and sec_uid has been the most
  // stable indicator across the variants we've seen.
  return extractDouyinSecUidFromState(state) !== "";
}
