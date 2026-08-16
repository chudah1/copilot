import type { TabId, ThesisSubTab } from "./position-helpers";

export function resolvePositionTabs(requestedTab: string | null): {
  activeTab: TabId;
  thesisSubTab: ThesisSubTab;
} {
  if (requestedTab === "monitoring") {
    return { activeTab: "monitoring", thesisSubTab: "thesis" };
  }
  if (requestedTab === "signals") {
    return { activeTab: "thesis", thesisSubTab: "signals" };
  }
  if (requestedTab === "decisions") {
    return { activeTab: "thesis", thesisSubTab: "log" };
  }
  return { activeTab: "thesis", thesisSubTab: "thesis" };
}

export function encodePositionTab(
  activeTab: TabId,
  thesisSubTab: ThesisSubTab,
): "monitoring" | "signals" | "decisions" | null {
  if (activeTab === "monitoring") return "monitoring";
  if (thesisSubTab === "signals") return "signals";
  if (thesisSubTab === "log") return "decisions";
  return null;
}
