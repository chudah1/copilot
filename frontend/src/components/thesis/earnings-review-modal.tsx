"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { ClaimVerdict, EarningsReviewResult } from "@/types";

interface EarningsReviewModalProps {
  thesisId: string;
  ticker: string;
  investorProfile?: "thesis_driven" | "hearsay_driven" | null;
  onClose: () => void;
}

const VERDICT_CONFIG = {
  holds: {
    label: "Holds",
    color: "#166534",
    bg: "#f0fdf4",
    border: "#bbf7d0",
    dot: "#16a34a",
  },
  watch: {
    label: "Watch",
    color: "#92400e",
    bg: "#fffbeb",
    border: "#fde68a",
    dot: "#d97706",
  },
  broken: {
    label: "Broken",
    color: "#7f1d1d",
    bg: "#fef2f2",
    border: "#fecaca",
    dot: "#dc2626",
  },
  unclear: {
    label: "Unclear",
    color: "#374151",
    bg: "#f9fafb",
    border: "#e5e7eb",
    dot: "#9ca3af",
  },
} as const;

function assessmentConfigForProfile(investorProfile?: "thesis_driven" | "hearsay_driven" | null) {
  if (investorProfile === "thesis_driven") {
    return {
      thesis_intact: {
        label: "Thesis Intact",
        color: "#166534",
        bg: "#f0fdf4",
        border: "#86efac",
        icon: "✓",
      },
      watch: {
        label: "Assumption to watch",
        color: "#92400e",
        bg: "#fffbeb",
        border: "#fde68a",
        icon: "⚠",
      },
      thesis_challenged: {
        label: "Thesis Challenged",
        color: "#7f1d1d",
        bg: "#fef2f2",
        border: "#fca5a5",
        icon: "✗",
      },
    } as const;
  }

  return {
    thesis_intact: {
      label: "Reason Intact",
      color: "#166534",
      bg: "#f0fdf4",
      border: "#86efac",
      icon: "✓",
    },
    watch: {
      label: "Worth Watching",
      color: "#92400e",
      bg: "#fffbeb",
      border: "#fde68a",
      icon: "⚠",
    },
    thesis_challenged: {
      label: investorProfile === "hearsay_driven" ? "Story Challenged" : "Reason Challenged",
      color: "#7f1d1d",
      bg: "#fef2f2",
      border: "#fca5a5",
      icon: "✗",
    },
  } as const;
}

function VerdictCard({ verdict }: { verdict: ClaimVerdict }) {
  const config = VERDICT_CONFIG[verdict.verdict] ?? VERDICT_CONFIG.unclear;
  return (
    <div
      style={{
        border: `1px solid ${config.border}`,
        backgroundColor: config.bg,
        borderRadius: "6px",
        padding: "16px",
        display: "flex",
        gap: "12px",
      }}
    >
      <div
        style={{
          width: "8px",
          height: "8px",
          borderRadius: "50%",
          backgroundColor: config.dot,
          marginTop: "6px",
          flexShrink: 0,
        }}
      />
      <div style={{ flex: 1 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: "8px",
            marginBottom: "8px",
          }}
        >
          <p
            style={{
              fontFamily: "'Instrument Sans', sans-serif",
              fontSize: "13px",
              color: "#374151",
              lineHeight: "1.5",
              margin: 0,
            }}
          >
            {verdict.claim_text}
          </p>
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: "10px",
              fontWeight: 600,
              color: config.color,
              backgroundColor: config.bg,
              border: `1px solid ${config.border}`,
              borderRadius: "4px",
              padding: "2px 6px",
              whiteSpace: "nowrap",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            {config.label}
          </span>
        </div>
        <p
          style={{
            fontFamily: "'Instrument Sans', sans-serif",
            fontSize: "13px",
            color: "#4b5563",
            lineHeight: "1.6",
            margin: "0 0 6px 0",
          }}
        >
          {verdict.explanation}
        </p>
        {verdict.evidence && (
          <p
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: "11px",
              color: "#6b7280",
              margin: 0,
            }}
          >
            {verdict.evidence}
          </p>
        )}
      </div>
    </div>
  );
}

export function EarningsReviewModal({
  thesisId,
  ticker,
  investorProfile,
  onClose,
}: EarningsReviewModalProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<EarningsReviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runReview = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.post<EarningsReviewResult>(`/api/theses/${thesisId}/earnings-review`);
      setResult(result);
    } catch (error: unknown) {
      setError(getErrorMessage(error, "Review failed"));
    } finally {
      setLoading(false);
    }
  };

  const assessmentMap = assessmentConfigForProfile(investorProfile);
  const assessmentConfig = result
    ? assessmentMap[result.overall_assessment] ?? assessmentMap.watch
    : null;
  const subtitle =
    investorProfile === "thesis_driven"
      ? `${ticker} — do the thesis assumptions still hold?`
      : investorProfile === "hearsay_driven"
        ? `${ticker} — does the original story still hold up as a reason?`
        : `${ticker} — does your reason still hold?`;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0,0,0,0.4)",
        zIndex: 50,
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        padding: "0",
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        style={{
          backgroundColor: "var(--card)",
          width: "100%",
          maxWidth: "680px",
          maxHeight: "90vh",
          borderRadius: "12px 12px 0 0",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "20px 24px 16px",
            borderBottom: "1px solid #e8e0d5",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
          }}
        >
          <div>
            <h2
              style={{
                fontFamily: "'Cormorant', serif",
                fontStyle: "italic",
                fontSize: "22px",
                fontWeight: 600,
                color: "#1a0f0a",
                margin: "0 0 2px 0",
              }}
            >
              Post-Earnings Review
            </h2>
            <p
              style={{
                fontFamily: "'Instrument Sans', sans-serif",
                fontSize: "13px",
                color: "#78716c",
                margin: 0,
              }}
            >
              {subtitle}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "#78716c",
              fontSize: "20px",
              padding: "4px",
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "24px" }}>
          {!result && !loading && (
            <div style={{ textAlign: "center", padding: "32px 0" }}>
              <p
                style={{
                  fontFamily: "'Cormorant', serif",
                  fontStyle: "italic",
                  fontSize: "18px",
                  color: "#44302a",
                  marginBottom: "12px",
                }}
              >
                Ready to check your reason against latest earnings.
              </p>
              <p
                style={{
                  fontFamily: "'Instrument Sans', sans-serif",
                  fontSize: "13px",
                  color: "#78716c",
                  marginBottom: "28px",
                  maxWidth: "360px",
                  margin: "0 auto 28px",
                  lineHeight: "1.6",
                }}
              >
                Claude will evaluate each of your reason&apos;s claims against the
                latest earnings data and tell you what still holds — and what
                doesn&apos;t.
              </p>
              {error && (
                <p
                  style={{
                    fontFamily: "'Instrument Sans', sans-serif",
                    fontSize: "13px",
                    color: "#dc2626",
                    marginBottom: "16px",
                  }}
                >
                  {error}
                </p>
              )}
              <button
                onClick={runReview}
                style={{
                  backgroundColor: "#5C2018",
                  color: "var(--primary-foreground)",
                  border: "none",
                  borderRadius: "6px",
                  padding: "10px 24px",
                  fontFamily: "'Instrument Sans', sans-serif",
                  fontSize: "14px",
                  fontWeight: 500,
                  cursor: "pointer",
                  letterSpacing: "0.01em",
                }}
              >
                Run Review
              </button>
            </div>
          )}

          {loading && (
            <div style={{ textAlign: "center", padding: "48px 0" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  border: "2px solid #e8e0d5",
                  borderTopColor: "#5C2018",
                  borderRadius: "50%",
                  animation: "spin 0.8s linear infinite",
                  margin: "0 auto 16px",
                }}
              />
              <p
                style={{
                  fontFamily: "'Instrument Sans', sans-serif",
                  fontSize: "13px",
                  color: "#78716c",
                }}
              >
                Evaluating your reason against latest earnings…
              </p>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          )}

          {result && assessmentConfig && (
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              {/* Overall assessment */}
              <div
                style={{
                  border: `1px solid ${assessmentConfig.border}`,
                  backgroundColor: assessmentConfig.bg,
                  borderRadius: "8px",
                  padding: "16px 20px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    marginBottom: "8px",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: "16px",
                      color: assessmentConfig.color,
                      fontWeight: 700,
                    }}
                  >
                    {assessmentConfig.icon}
                  </span>
                  <span
                    style={{
                      fontFamily: "'Instrument Sans', sans-serif",
                      fontSize: "13px",
                      fontWeight: 600,
                      color: assessmentConfig.color,
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                    }}
                  >
                    {assessmentConfig.label}
                  </span>
                  {result.fiscal_quarter && (
                    <span
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: "11px",
                        color: "#9ca3af",
                        marginLeft: "auto",
                      }}
                    >
                      {result.fiscal_quarter}
                      {result.earnings_surprise_pct !== null &&
                        ` · ${result.earnings_surprise_pct > 0 ? "+" : ""}${result.earnings_surprise_pct.toFixed(1)}% surprise`}
                    </span>
                  )}
                </div>
                <p
                  style={{
                    fontFamily: "'Instrument Sans', sans-serif",
                    fontSize: "14px",
                    color: "#1a0f0a",
                    lineHeight: "1.65",
                    margin: 0,
                  }}
                >
                  {result.summary}
                </p>
              </div>

              {/* Claim verdicts */}
              {result.verdicts.length > 0 && (
                <div>
                  <p
                    style={{
                      fontFamily: "'Instrument Sans', sans-serif",
                      fontSize: "11px",
                      fontWeight: 600,
                      color: "#9ca3af",
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      marginBottom: "10px",
                    }}
                  >
                    Claim-by-Claim
                  </p>
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {result.verdicts.map((v) => (
                      <VerdictCard key={v.claim_id} verdict={v} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        {result && (
          <div
            style={{
              padding: "16px 24px",
              borderTop: "1px solid #e8e0d5",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <p
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: "10px",
                color: "#a8a29e",
                margin: 0,
              }}
            >
              Saved to conviction log
            </p>
            <button
              onClick={onClose}
              style={{
                backgroundColor: "transparent",
                color: "#5C2018",
                border: "1px solid #5C2018",
                borderRadius: "6px",
                padding: "8px 20px",
                fontFamily: "'Instrument Sans', sans-serif",
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
