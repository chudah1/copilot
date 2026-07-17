import type {
  ConvictionLogResponse,
  Holding,
  HoldingPulse,
  MonitoringEvent,
  MonitoringGap,
  OnboardingState,
  PortfolioPulse,
  ReviewedItem,
  SupportingItem,
  Thesis,
  ThesisDecompositionEnvelope,
  UpcomingEarnings,
} from "@/types";

export interface PositionWorkspaceReader {
  get<T>(path: string): Promise<T>;
}

export interface PositionWorkspaceSnapshot {
  holdings: Holding[];
  holding: Holding | null;
  theses: Thesis[];
  activeThesis: Thesis | undefined;
  events: MonitoringEvent[];
  convictionLog: ConvictionLogResponse | null;
  upcomingEarnings: UpcomingEarnings | null;
  onboardingState: OnboardingState | null;
  monitoringGaps: MonitoringGap[];
  pulse: HoldingPulse | null;
  reviewedItems: ReviewedItem[];
  supportingItems: SupportingItem[];
  decompositionEnvelope: ThesisDecompositionEnvelope | null;
}

export async function loadPositionWorkspace(
  reader: PositionWorkspaceReader,
  ticker: string,
): Promise<PositionWorkspaceSnapshot> {
  const holdings = await reader.get<Holding[]>("/api/portfolio/holdings");
  const holding = holdings.find((item) => item.ticker === ticker) ?? null;
  if (!holding) return emptySnapshot(holdings);

  const [
    theses,
    events,
    convictionLog,
    earnings,
    onboardingState,
    monitoringGaps,
    portfolioPulse,
    reviewedItems,
    supportingItems,
  ] = await Promise.all([
    reader.get<Thesis[]>(`/api/theses/holding/${holding.id}`),
    reader.get<MonitoringEvent[]>(`/api/monitoring/holdings/${holding.id}/events`),
    optional(reader.get<ConvictionLogResponse>(`/api/portfolio/holdings/${holding.id}/conviction-log`), null),
    optional(reader.get<UpcomingEarnings[]>("/api/portfolio/upcoming-earnings"), []),
    optional(reader.get<OnboardingState>("/api/onboarding/state"), null),
    optional(reader.get<MonitoringGap[]>("/api/monitoring/gaps"), []),
    optional(reader.get<PortfolioPulse>("/api/portfolio/pulse"), null),
    optional(reader.get<ReviewedItem[]>(`/api/monitoring/holdings/${holding.id}/reviewed`), []),
    optional(reader.get<SupportingItem[]>(`/api/monitoring/holdings/${holding.id}/supporting`), []),
  ]);
  const activeThesis = selectActiveThesis(theses);
  const decompositionEnvelope = activeThesis
    ? await loadDecomposition(reader, activeThesis.id)
    : null;

  return {
    holdings,
    holding,
    theses,
    activeThesis,
    events,
    convictionLog,
    upcomingEarnings: earnings.find((item) => item.holding_id === holding.id) ?? null,
    onboardingState,
    monitoringGaps,
    pulse: portfolioPulse?.pulses.find((item) => item.holding_id === holding.id) ?? null,
    reviewedItems,
    supportingItems,
    decompositionEnvelope,
  };
}

export function selectActiveThesis(theses: Thesis[]) {
  return theses.find((thesis) =>
    thesis.status === "active" || thesis.status === "draft" || thesis.status === "needs_review"
  );
}

export function selectLatestInvalidatedThesis(theses: Thesis[]) {
  return [...theses]
    .filter((thesis) => thesis.status === "invalidated")
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())[0];
}

async function loadDecomposition(reader: PositionWorkspaceReader, thesisId: string) {
  try {
    return await reader.get<ThesisDecompositionEnvelope>(`/api/theses/${thesisId}/decomposition`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to load decomposition";
    return message.includes("Decomposition not found")
      ? null
      : { status: "failed", message, decomposition: null } satisfies ThesisDecompositionEnvelope;
  }
}

async function optional<T>(request: Promise<T>, fallback: T): Promise<T> {
  try {
    return await request;
  } catch {
    return fallback;
  }
}

function emptySnapshot(holdings: Holding[]): PositionWorkspaceSnapshot {
  return {
    holdings,
    holding: null,
    theses: [],
    activeThesis: undefined,
    events: [],
    convictionLog: null,
    upcomingEarnings: null,
    onboardingState: null,
    monitoringGaps: [],
    pulse: null,
    reviewedItems: [],
    supportingItems: [],
    decompositionEnvelope: null,
  };
}
