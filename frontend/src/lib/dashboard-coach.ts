import { formatAssumptionLabel } from "./assumption-label.ts";
import { positionBlindSpotHref, positionDetailHref } from "./position-links.ts";
import type {
  DashboardBlindSpot,
  DashboardCoachMemory,
  DashboardDecisionMemory,
  DashboardOpenLoop,
  DashboardWorkspace,
  DashboardWorkspaceItem,
} from "../types/index.ts";

function cleanTicker(ticker: string) {
  return ticker.replace(/_US_EQ$/i, "").replace(/_EQ$/i, "");
}

export interface DashboardCoachPlan {
  mode: "pattern_under_pressure" | "close_open_loop" | "sharpen_case" | "pattern_watch" | "learning";
  tone: "warning" | "focus" | "calm";
  adviceKey: string;
  feedback: {
    mode: string;
    holdingId: string | null;
    thesisId: string | null;
    loopKey: string | null;
    patternKind: string | null;
  };
  eyebrow: string;
  chip: string;
  title: string;
  body: string;
  context: string;
  primaryCta: {
    href: string;
    label: string;
  };
  secondaryCta?: {
    href: string;
    label: string;
  };
  stats: Array<{
    label: string;
    value: string;
  }>;
}

function positionHref(item: DashboardWorkspaceItem) {
  if (item.decision_state === "needs_written_case") {
    return positionBlindSpotHref(item.holding.ticker);
  }
  if (item.decision_state === "needs_decision" || item.decision_state === "changed") {
    return positionDetailHref(item.holding.ticker, { tab: "monitoring" });
  }
  return positionDetailHref(item.holding.ticker);
}

function patternHref(memory: DashboardDecisionMemory) {
  switch (memory.primary_pattern?.kind) {
    case "attention":
      return "/dashboard/quarterly-review?pattern=attention#decision-patterns";
    case "conviction":
      return "/dashboard/quarterly-review?pattern=conviction#decision-patterns";
    case "exit":
      return "/dashboard/quarterly-review?pattern=exit#decision-patterns";
    default:
      return "/dashboard/quarterly-review#decision-patterns";
  }
}

function investorWord(investorProfile: DashboardWorkspace["investor_profile"]) {
  return investorProfile === "hearsay_driven" ? "story" : investorProfile === "thesis_driven" ? "thesis" : "reason";
}

function assumptionLabel(
  item: DashboardWorkspaceItem | null,
  investorProfile: DashboardWorkspace["investor_profile"],
) {
  return formatAssumptionLabel(item?.assumption_label, investorProfile, {
    maxLength: 64,
    sentenceCaseFallback: true,
  });
}

function loopCountContext(loops: DashboardOpenLoop[]) {
  if (loops.length <= 1) return "1 loop is still open across the portfolio.";
  return `${loops.length} loops are still open across the portfolio.`;
}

function coachOutcomeSummary(memory: DashboardCoachMemory | null | undefined, mode: string) {
  const modeStats = memory?.mode_stats[mode];
  if (!modeStats || modeStats.resolved_count === 0) return null;

  if (modeStats.hurt_count > modeStats.helpful_count) {
    return "Similar acted prompts have more often aged badly than cleanly. PenKeep is pushing for tighter closure now.";
  }
  if (modeStats.helpful_count > 0) {
    return `When you acted on similar prompts, the later read held up ${modeStats.helpful_count} time${modeStats.helpful_count === 1 ? "" : "s"}.`;
  }
  return `PenKeep has ${modeStats.resolved_count} resolved prompt${modeStats.resolved_count === 1 ? "" : "s"} of this type to learn from.`;
}

function coachMemoryNote(memory: DashboardCoachMemory | null | undefined, mode: string) {
  if (!memory) return null;
  const modeStats = memory.mode_stats[mode];
  if (!modeStats) return null;

  const outcomeSummary = coachOutcomeSummary(memory, mode);
  if (outcomeSummary) return outcomeSummary;

  if (
    memory.last_feedback === "skipped" &&
    memory.last_mode === mode &&
    modeStats.skipped_count > 0
  ) {
    return `You skipped ${modeStats.skipped_count} similar prompt${modeStats.skipped_count === 1 ? "" : "s"} before this one, so PenKeep is narrowing the next move instead of broadening the read.`;
  }

  if (
    memory.last_feedback === "acted" &&
    memory.last_mode === mode &&
    modeStats.acted_count > 0
  ) {
    return "You usually act on this kind of prompt. PenKeep is leaning into the shortest path to the next decision.";
  }

  return null;
}

function coachLearningStat(memory: DashboardCoachMemory | null | undefined, mode: string) {
  const modeStats = memory?.mode_stats[mode];
  if (!modeStats) return null;
  if (modeStats.resolved_count > 0) {
    if (modeStats.hurt_count > modeStats.helpful_count) {
      return { label: "Turned worse", value: String(modeStats.hurt_count) };
    }
    return { label: "Held up", value: String(modeStats.helpful_count) };
  }
  if (modeStats.acted_count > 0) {
    return { label: "Taken before", value: String(modeStats.acted_count) };
  }
  return null;
}

function coachAvoidanceStat(memory: DashboardCoachMemory | null | undefined, mode: string) {
  const modeStats = memory?.mode_stats[mode];
  if (!modeStats) return null;
  if (modeStats.resolved_count > 0 && modeStats.hurt_count > 0) {
    return { label: "Turned worse", value: String(modeStats.hurt_count) };
  }
  if (modeStats.skipped_count > 0) {
    return { label: "Skipped before", value: String(modeStats.skipped_count) };
  }
  return null;
}

function compactStats(
  stats: Array<
    | {
        label: string;
        value: string;
      }
    | null
  >,
) {
  return stats.filter((stat): stat is { label: string; value: string } => Boolean(stat));
}

function patternPressureContext(args: {
  memory: DashboardDecisionMemory;
  topDecision: DashboardWorkspaceItem;
  openLoops: DashboardOpenLoop[];
  investorProfile: DashboardWorkspace["investor_profile"];
}) {
  const { memory, topDecision, openLoops, investorProfile } = args;
  const ticker = cleanTicker(topDecision.holding.ticker);
  const assumption = assumptionLabel(topDecision, investorProfile);
  const loopTail = openLoops.length > 0 ? ` ${loopCountContext(openLoops)}` : "";

  switch (memory.primary_pattern?.kind) {
    case "attention":
      return `${ticker} is testing ${assumption}. Your recent pattern is to notice the early warning, then leave it unresolved until the pressure compounds.${loopTail}`;
    case "conviction":
      return `${ticker} is testing ${assumption}. Your recent pattern is to keep holding while the same question stays open, which makes closure more important than another read.${loopTail}`;
    case "exit":
      return `${ticker} is testing ${assumption}. Your recent pattern is to let pressure build until the next move is forced into an exit decision.${loopTail}`;
    default:
      return `${ticker} is getting tested right now. ${assumption} is the question under stress.${loopTail}`;
  }
}

function sharpenCaseContext(
  blindSpot: DashboardBlindSpot,
  investorProfile: DashboardWorkspace["investor_profile"],
) {
  const ticker = cleanTicker(blindSpot.holding.ticker);
  const caseWord = investorWord(investorProfile);
  if (blindSpot.blind_spot_kind === "missing") {
    return `${ticker} still has no ${caseWord}. If the market moves first, the price will be visible before your reasoning is.`;
  }
  if (blindSpot.blind_spot_kind === "review_overdue") {
    return `${ticker} is outside its review cadence. Before the next catalyst lands, refresh what still has to be true and what would break it.`;
  }
  return `${ticker} has a ${caseWord}, but it is still too vague to coach future-you when pressure shows up.`;
}

function blindSpotContextLine(
  blindSpots: DashboardBlindSpot[],
  primaryBlindSpot: DashboardBlindSpot,
  caseWord: string,
) {
  const missingCount = blindSpots.filter((spot) => spot.blind_spot_kind === "missing").length;
  const reviewOverdueCount = blindSpots.filter((spot) => spot.blind_spot_kind === "review_overdue").length;
  const tightenCount = blindSpots.filter(
    (spot) => spot.blind_spot_kind === "weak" || spot.blind_spot_kind === "workable",
  ).length;

  if (blindSpots.length === 1) {
    switch (primaryBlindSpot.blind_spot_kind) {
      case "missing":
        return `This is the only position still missing a ${caseWord}.`;
      case "review_overdue":
        return `This is the only ${caseWord} sitting outside its review cadence right now.`;
      default:
        return `This is the main ${caseWord} that still needs one cleaner rule.`;
    }
  }

  const parts: string[] = [];
  if (missingCount > 0) {
    parts.push(`${missingCount} missing`);
  }
  if (tightenCount > 0) {
    parts.push(`${tightenCount} to clarify`);
  }
  if (reviewOverdueCount > 0) {
    parts.push(`${reviewOverdueCount} overdue`);
  }

  if (parts.length === 0) {
    return `${blindSpots.length} positions still need a clearer or fresher ${caseWord}.`;
  }

  return `${blindSpots.length} positions need attention: ${parts.join(" · ")}.`;
}

function blindSpotPrimaryStat(
  blindSpots: DashboardBlindSpot[],
  primaryBlindSpot: DashboardBlindSpot,
  caseWord: string,
) {
  switch (primaryBlindSpot.blind_spot_kind) {
    case "missing": {
      const missingCount = blindSpots.filter((spot) => spot.blind_spot_kind === "missing").length;
      return { label: `Missing ${caseWord}s`, value: String(missingCount) };
    }
    case "review_overdue": {
      const reviewOverdueCount = blindSpots.filter((spot) => spot.blind_spot_kind === "review_overdue").length;
      return { label: "Review overdue", value: String(reviewOverdueCount) };
    }
    default: {
      const tightenCount = blindSpots.filter(
        (spot) => spot.blind_spot_kind === "weak" || spot.blind_spot_kind === "workable",
      ).length;
      return { label: `To clarify`, value: String(tightenCount) };
    }
  }
}

export function deriveDashboardCoach(args: {
  workspace: DashboardWorkspace;
  openLoops: DashboardOpenLoop[];
  coachMemory?: DashboardCoachMemory | null;
}): DashboardCoachPlan {
  const { workspace, openLoops, coachMemory = null } = args;
  const { decision_memory: memory, top_decision: topDecision, blind_spots: blindSpots, investor_profile: investorProfile } = workspace;
  const caseWord = investorWord(investorProfile);
  const primaryBlindSpot = blindSpots[0] ?? null;
  const reviewHref = memory.has_pattern ? patternHref(memory) : "/dashboard/quarterly-review#decision-patterns";

  if (
    memory.has_pattern &&
    memory.primary_pattern &&
    topDecision &&
    (topDecision.decision_state === "needs_decision" || topDecision.decision_state === "changed")
  ) {
    const mode = "pattern_under_pressure";
    return {
      mode,
      tone: "warning",
      adviceKey: `${mode}:${topDecision.holding.id}:${memory.primary_pattern.kind}`,
      feedback: {
        mode,
        holdingId: topDecision.holding.id,
        thesisId: topDecision.thesis_id,
        loopKey: openLoops[0]?.loop_key ?? null,
        patternKind: memory.primary_pattern.kind,
      },
      eyebrow: "Next move",
      chip: "Pattern showing up",
      title: `${cleanTicker(topDecision.holding.ticker)} is where your pattern meets the market.`,
      body: patternPressureContext({ memory, topDecision, openLoops, investorProfile }),
      context: coachMemoryNote(coachMemory, mode) ?? `Seen ${memory.primary_pattern.instances} times across ${memory.resolved_count} tested decision${memory.resolved_count === 1 ? "" : "s"}.`,
      primaryCta: {
        href: positionHref(topDecision),
        label: `Resolve ${cleanTicker(topDecision.holding.ticker)} now`,
      },
      secondaryCta: {
        href: reviewHref,
        label: "Review the pattern",
      },
      stats: compactStats([
        { label: "Follow-ups", value: String(openLoops.length) },
        coachLearningStat(coachMemory, mode),
      ]),
    };
  }

  if (openLoops.length > 0) {
    const firstLoop = openLoops[0];
    const moreCount = openLoops.length - 1;
    const mode = "close_open_loop";
    return {
      mode,
      tone: "focus",
      adviceKey: `${mode}:${firstLoop.loop_key}`,
      feedback: {
        mode,
        holdingId: firstLoop.holding_id,
        thesisId: firstLoop.thesis_id,
        loopKey: firstLoop.loop_key,
        patternKind: memory.primary_pattern?.kind ?? null,
      },
      eyebrow: "Next move",
      chip: "Close it out",
      title: `${cleanTicker(firstLoop.ticker)} still needs closure.`,
      body: `${firstLoop.detail}${moreCount > 0 ? ` ${moreCount} more ${moreCount === 1 ? "follow-up is" : "follow-ups are"} waiting behind it.` : ""}`,
      context: coachMemoryNote(coachMemory, mode) ?? (memory.has_pattern
        ? `Your strongest pattern right now: ${memory.primary_pattern?.headline}`
        : loopCountContext(openLoops)),
      primaryCta: {
        href: firstLoop.cta_href,
        label: firstLoop.cta_label,
      },
      secondaryCta: {
        href: reviewHref,
        label: memory.has_pattern ? "See why this pattern repeats" : "Open quarterly review",
      },
      stats: compactStats([
        { label: "Follow-ups", value: String(openLoops.length) },
        coachAvoidanceStat(coachMemory, mode),
      ]),
    };
  }

  if (primaryBlindSpot) {
    const mode = "sharpen_case";
    return {
      mode,
      tone: "focus",
      adviceKey: `${mode}:${primaryBlindSpot.holding.id}:${primaryBlindSpot.blind_spot_kind}`,
      feedback: {
        mode,
        holdingId: primaryBlindSpot.holding.id,
        thesisId: primaryBlindSpot.thesis_id,
        loopKey: null,
        patternKind: memory.primary_pattern?.kind ?? null,
      },
      eyebrow: "Next move",
      chip: `Sharpen the ${caseWord}`,
      title: `Tighten ${cleanTicker(primaryBlindSpot.holding.ticker)} before it gets tested.`,
      body: sharpenCaseContext(primaryBlindSpot, investorProfile),
      context: coachMemoryNote(coachMemory, mode) ?? blindSpotContextLine(blindSpots, primaryBlindSpot, caseWord),
      primaryCta: {
        href:
          primaryBlindSpot.blind_spot_kind === "missing"
            ? positionBlindSpotHref(primaryBlindSpot.holding.ticker)
            : positionDetailHref(primaryBlindSpot.holding.ticker),
        label: primaryBlindSpot.blind_spot_kind === "missing" ? `Write ${cleanTicker(primaryBlindSpot.holding.ticker)}` : `Tighten ${cleanTicker(primaryBlindSpot.holding.ticker)}`,
      },
      secondaryCta: {
        href: "/dashboard",
        label: "Review the inbox",
      },
      stats: compactStats([
        blindSpotPrimaryStat(blindSpots, primaryBlindSpot, caseWord),
        coachLearningStat(coachMemory, mode),
      ]),
    };
  }

  if (memory.has_pattern && memory.primary_pattern) {
    const mode = "pattern_watch";
    return {
      mode,
      tone: memory.primary_pattern.tone === "calm" ? "calm" : "focus",
      adviceKey: `${mode}:${memory.primary_pattern.kind}`,
      feedback: {
        mode,
        holdingId: topDecision?.holding.id ?? null,
        thesisId: topDecision?.thesis_id ?? null,
        loopKey: null,
        patternKind: memory.primary_pattern.kind,
      },
      eyebrow: "Next move",
      chip: "Pattern watch",
      title: "Your next decision will probably rhyme with the last few.",
      body: memory.primary_pattern.detail,
      context: coachMemoryNote(coachMemory, mode) ?? `PenKeep has ${memory.resolved_count} tested decisions to learn from, and ${memory.open_followups_count} are still open.`,
      primaryCta: {
        href: reviewHref,
        label: "Review your pattern",
      },
      secondaryCta: {
        href: "/dashboard/quarterly-review",
        label: "Run a quarterly review",
      },
      stats: compactStats([
        { label: "Seen", value: `${memory.primary_pattern.instances}x` },
        { label: "Resolved", value: String(memory.resolved_count) },
      ]),
    };
  }

  const mode = "learning";
  return {
    mode,
    tone: "calm",
    adviceKey: `${mode}:${workspace.summary_metrics.holdings_count}`,
    feedback: {
      mode,
      holdingId: topDecision?.holding.id ?? null,
      thesisId: topDecision?.thesis_id ?? null,
      loopKey: null,
      patternKind: memory.primary_pattern?.kind ?? null,
    },
    eyebrow: "Next move",
    chip: "Still learning",
    title: "PenKeep is still learning how you decide.",
    body: `Close a few live decisions and keep sharpening what you wrote. Once outcomes accumulate, the dashboard will start teaching your patterns, not just tracking your holdings.`,
    context: coachMemoryNote(coachMemory, mode) ?? `${workspace.recent_decisions.length} recent decision${workspace.recent_decisions.length === 1 ? "" : "s"} recorded so far.`,
    primaryCta: {
      href: "/dashboard/quarterly-review",
      label: "Start quarterly review",
    },
    secondaryCta: {
      href: "/digests",
      label: "Open digest archive",
    },
    stats: compactStats([
      memory.resolved_count > 0 ? { label: "Resolved", value: String(memory.resolved_count) } : null,
      openLoops.length > 0 ? { label: "Follow-ups", value: String(openLoops.length) } : null,
    ]),
  };
}
