import type {
  DashboardCoachMemory,
  DashboardDecisionMemory,
} from "@/types";

export function patternKindCopy(kind: string | null | undefined) {
  switch (kind) {
    case "attention":
      return {
        chip: "Attention pattern",
        href: "/dashboard/quarterly-review?pattern=attention#decision-patterns",
      };
    case "conviction":
      return {
        chip: "Holding pattern",
        href: "/dashboard/quarterly-review?pattern=conviction#decision-patterns",
      };
    case "exit":
      return {
        chip: "Exit pattern",
        href: "/dashboard/quarterly-review?pattern=exit#decision-patterns",
      };
    default:
      return {
        chip: "Learning",
        href: "/dashboard/quarterly-review#decision-patterns",
      };
  }
}

export function aggregateCoachOutcomes(coachMemory: DashboardCoachMemory | null | undefined) {
  if (!coachMemory) return null;
  return Object.values(coachMemory.mode_stats).reduce(
    (summary, stats) => {
      summary.resolved += stats.resolved_count;
      summary.helpful += stats.helpful_count;
      summary.hurt += stats.hurt_count;
      summary.acted += stats.acted_count;
      summary.skipped += stats.skipped_count;
      return summary;
    },
    { resolved: 0, helpful: 0, hurt: 0, acted: 0, skipped: 0 },
  );
}

export function coachOutcomeCopy(coachMemory: DashboardCoachMemory | null | undefined) {
  const summary = aggregateCoachOutcomes(coachMemory);
  if (!summary) return null;
  if (summary.resolved > 0) {
    if (summary.hurt > summary.helpful) {
      return {
        body: `Across ${summary.resolved} resolved coach suggestion${summary.resolved === 1 ? "" : "s"}, later reads more often stayed under pressure than clearly improved.`,
        summary,
      };
    }
    if (summary.helpful > 0) {
      return {
        body: `Across ${summary.resolved} resolved coach suggestion${summary.resolved === 1 ? "" : "s"}, later reads usually improved after you acted.`,
        summary,
      };
    }
    return {
      body: `PenKeep has ${summary.resolved} resolved coach suggestion${summary.resolved === 1 ? "" : "s"} recorded so far, but not enough signal yet to judge the pattern clearly.`,
      summary,
    };
  }
  if (summary.acted > 0) {
    return {
      body: `PenKeep has seen you act on ${summary.acted} coach suggestion${summary.acted === 1 ? "" : "s"} so far. Once those decisions age into outcomes, this section will show what usually followed.`,
      summary,
    };
  }
  return null;
}

export function decisionMemoryCta(memory: DashboardDecisionMemory) {
  if (memory.has_pattern) return "Review this pattern";
  if (memory.resolved_count > 0) return "See recent decisions";
  return "Open quarterly review";
}
