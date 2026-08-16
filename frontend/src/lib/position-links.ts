export function positionDetailHref(
  ticker: string,
  options?: { source?: "dashboard_blind_spot"; tab?: string },
) {
  const params = new URLSearchParams();
  if (options?.source) {
    params.set("source", options.source);
  }
  if (options?.tab) {
    params.set("tab", options.tab);
  }
  const query = params.toString();
  return `/dashboard/positions/${ticker}${query ? `?${query}` : ""}`;
}

export function positionBlindSpotHref(ticker: string) {
  return positionDetailHref(ticker, { source: "dashboard_blind_spot" });
}

export function positionThesisEditorHref(ticker: string) {
  return `/dashboard/positions/${ticker}?tab=thesis&edit=1`;
}

export function positionMonitoringHref(ticker: string) {
  return positionDetailHref(ticker, { tab: "monitoring" });
}

export function positionDecisionTrailHref(ticker: string) {
  return positionDetailHref(ticker, { tab: "decisions" });
}
