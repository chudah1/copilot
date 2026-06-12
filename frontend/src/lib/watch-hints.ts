const METRIC_LABELS: Record<string, string> = {
  revenue_growth_yoy: "Revenue growth",
  earnings_growth_yoy: "Earnings growth",
  pe_ratio: "P/E ratio",
  dividend_yield: "Dividend yield",
  gross_margin: "Gross margin",
  operating_margin: "Operating margin",
  debt_to_equity: "Debt / equity",
};

type PriceStyle = "review" | "discipline";

function toSentenceCaseLabel(label: string): string {
  return label ? `${label.charAt(0).toLowerCase()}${label.slice(1)}` : label;
}

function formatThresholdValue(unit: string | undefined, threshold: number): string {
  if (unit === "pct") {
    const pct = Math.abs(threshold) <= 1 ? threshold * 100 : threshold;
    return `${pct % 1 === 0 ? pct.toFixed(0) : pct.toFixed(1)}%`;
  }
  return String(threshold);
}

function inferMetricBreachDirection(
  operator: string,
  rationale: string | undefined,
): "below" | "above" | "drift" {
  const text = (rationale || "").toLowerCase();

  if (
    /(falls?|falling|drops?|dropping|slips?|slipping|below|stalling|weakens?)/.test(text)
  ) {
    return "below";
  }
  if (
    /(rises?|rising|jumps?|jumping|spikes?|spiking|above|overheats?|too high|too expensive|expands?)/.test(text)
  ) {
    return "above";
  }

  if (operator === ">=" || operator === ">") return "below";
  if (operator === "<=" || operator === "<") return "above";
  return "drift";
}

export function describeWatchHint(
  hint: Record<string, unknown>,
  options?: { priceStyle?: PriceStyle },
): string | null {
  const priceStyle = options?.priceStyle ?? "review";

  if (hint.kind === "price_move_pct" && typeof hint.threshold === "number") {
    const threshold = Math.abs(hint.threshold);
    return priceStyle === "discipline"
      ? `Price discipline if the stock moves ${threshold}% or more.`
      : `Review if price moves ${threshold}% or more.`;
  }

  if (
    hint.kind === "metric_threshold" &&
    typeof hint.metric === "string" &&
    typeof hint.operator === "string" &&
    typeof hint.threshold === "number"
  ) {
    const label =
      typeof hint.label === "string"
        ? hint.label
        : (METRIC_LABELS[hint.metric] ?? hint.metric.replaceAll("_", " "));
    const proxyFor =
      typeof hint.proxy_for === "string" && hint.proxy_for.trim().length > 0
        ? hint.proxy_for.trim()
        : null;
    const unit =
      typeof hint.unit === "string"
        ? hint.unit
        : hint.metric === "revenue_growth_yoy" ||
            hint.metric === "earnings_growth_yoy" ||
            hint.metric === "gross_margin"
          ? "pct"
          : undefined;
    const thresholdText = formatThresholdValue(unit, hint.threshold);
    const direction = inferMetricBreachDirection(
      hint.operator,
      typeof hint.rationale === "string" ? hint.rationale : undefined,
    );

    if (hint.threshold === 0) {
      return proxyFor
        ? `Track ${toSentenceCaseLabel(label)} as a proxy for ${proxyFor}.`
        : null;
    }

    if (direction === "below") {
      return proxyFor
        ? `Review if ${label} falls below ${thresholdText}, using it as a proxy for ${proxyFor}.`
        : `Review if ${label} falls below ${thresholdText}.`;
    }
    if (direction === "above") {
      return proxyFor
        ? `Review if ${label} rises above ${thresholdText}, using it as a proxy for ${proxyFor}.`
        : `Review if ${label} rises above ${thresholdText}.`;
    }
    return proxyFor
      ? `Review if ${label} drifts away from ${thresholdText}, using it as a proxy for ${proxyFor}.`
      : `Review if ${label} drifts away from ${thresholdText}.`;
  }

  if (
    hint.kind === "news_watch" &&
    typeof hint.watch_for === "string" &&
    hint.watch_for.trim()
  ) {
    const watchFor = hint.watch_for.trim().replace(/[.]+$/, "");
    return `Review if ${watchFor}.`;
  }

  return null;
}
