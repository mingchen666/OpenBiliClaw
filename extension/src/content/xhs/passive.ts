/**
 * xhs passive URL collector — pure helpers.
 *
 * Extracts note URLs from anchors that are already rendered into (or just
 * outside) the viewport as the user browses. The collector never scrolls
 * — it only reacts to the user's own scrolling. Auto-scroll bots are a
 * textbook xhs risk-control signal, so we stay strictly passive.
 *
 * Every helper here is framework-free so tests can feed in minimal
 * anchor-like objects under node --test.
 */

/** Note detail URL variants xhs exposes. We accept any non-empty segment
 *  after the prefix; backend validation can tighten the id shape. */
const NOTE_PATH_PATTERNS = [/^\/explore\/[^/?#]+/i, /^\/discovery\/item\/[^/?#]+/i];

/** Query params we preserve. xsec_token is required by xhs detail APIs. */
const PRESERVED_QUERY_PARAMS = new Set(["xsec_token"]);

const DEFAULT_TOLERANCE_BELOW_PX = 0;
const DEFAULT_TOLERANCE_ABOVE_PX = 0;

export type XhsPageType = "search" | "profile" | "note" | "explore" | "other";

export interface ViewportRect {
  top: number;
  bottom: number;
  height: number;
}

export interface AnchorLike {
  href: string;
  rect: DOMRect;
}

export interface CollectOptions {
  baseUrl: string;
  /** Extra px below viewport to still count as "visible" (for lazy-loaded rows). */
  toleranceBelowPx?: number;
  /** Extra px above viewport — lets the collector catch cards just scrolled past. */
  toleranceAbovePx?: number;
}

export interface XhsUrlObservation {
  urls: string[];
  page_type: XhsPageType;
  observed_at: number;
}

export function classifyXhsPageType(url: string): XhsPageType {
  if (url.includes("/search_result")) return "search";
  if (url.includes("/user/profile/")) return "profile";
  if (url.includes("/explore/") || url.includes("/discovery/item/")) return "note";
  if (url.includes("/explore")) return "explore";
  return "other";
}

function matchesNotePath(pathname: string): boolean {
  return NOTE_PATH_PATTERNS.some((pattern) => pattern.test(pathname));
}

export function extractXhsNoteUrl(href: string, baseUrl: string): string | null {
  if (!href || href.startsWith("javascript:") || href.startsWith("mailto:")) {
    return null;
  }

  let parsed: URL;
  try {
    parsed = new URL(href, baseUrl);
  } catch {
    return null;
  }

  if (!matchesNotePath(parsed.pathname)) return null;

  const keptParams = new URLSearchParams();
  parsed.searchParams.forEach((value, key) => {
    if (PRESERVED_QUERY_PARAMS.has(key)) {
      keptParams.set(key, value);
    }
  });

  const query = keptParams.toString();
  return `${parsed.origin}${parsed.pathname}${query ? `?${query}` : ""}`;
}

function isWithinViewport(
  rect: DOMRect,
  viewport: ViewportRect,
  toleranceAbovePx: number,
  toleranceBelowPx: number,
): boolean {
  const upperBound = viewport.bottom + toleranceBelowPx;
  const lowerBound = viewport.top - toleranceAbovePx;
  return rect.bottom >= lowerBound && rect.top <= upperBound;
}

export function collectInViewportNoteUrls(
  anchors: Iterable<AnchorLike>,
  viewport: ViewportRect,
  options: CollectOptions,
): string[] {
  const toleranceBelow = options.toleranceBelowPx ?? DEFAULT_TOLERANCE_BELOW_PX;
  const toleranceAbove = options.toleranceAbovePx ?? DEFAULT_TOLERANCE_ABOVE_PX;

  const ordered: string[] = [];
  const seen = new Set<string>();

  for (const anchor of anchors) {
    if (!isWithinViewport(anchor.rect, viewport, toleranceAbove, toleranceBelow)) {
      continue;
    }
    const url = extractXhsNoteUrl(anchor.href, options.baseUrl);
    if (!url || seen.has(url)) continue;
    seen.add(url);
    ordered.push(url);
  }

  return ordered;
}

/**
 * Remove URLs already present in ``seen`` and record the fresh ones in it.
 *
 * This gives each content-script page-session a monotonic "urls I've
 * already reported" record so we don't re-POST the same batch every time
 * the user scrolls.
 */
export function dedupeObservedUrls(urls: Iterable<string>, seen: Set<string>): string[] {
  const fresh: string[] = [];
  for (const url of urls) {
    if (seen.has(url)) continue;
    seen.add(url);
    fresh.push(url);
  }
  return fresh;
}
