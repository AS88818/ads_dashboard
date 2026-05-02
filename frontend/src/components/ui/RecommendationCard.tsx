"use client";

import React, { useState } from "react";
import { DashboardMetrics, Recommendation } from "@/lib/types";
import { CheckCircle2, XCircle, Zap, Loader2, Target, TrendingUp, Wrench, AlertCircle, Layers } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type CardStatus = "pending" | "applying" | "applied" | "manual_confirmed" | "dismissed";

const ACTION_TYPE_LABELS: Record<string, string> = {
  add_negative_keyword: "Add Negative Keyword",
  budget_adjustment: "Budget Adjustment",
  bid_adjustment: "Bid Adjustment",
  a_b_test: "A/B Test",
  keyword_action: "Keyword Action",
  pause: "Pause",
  scale_budget: "Scale Budget",
  review: "Review",
  switch_objective: "Switch Objective",
  review_overspend: "Review Overspend",
};

const QUALITY_STYLES: Record<string, string> = {
  "High confidence": "bg-green-50 text-green-700 border-green-100",
  "Needs review": "bg-amber-50 text-amber-700 border-amber-100",
  "Manual only": "bg-blue-50 text-blue-700 border-blue-100",
  "Insufficient data": "bg-gray-50 text-gray-600 border-gray-100",
};

export function RecommendationCard({
  recommendation: rec,
  clientName,
  baselineMetrics,
}: {
  recommendation: Recommendation;
  clientName?: string;
  baselineMetrics?: DashboardMetrics;
}) {
  const [cardStatus, setCardStatus] = useState<CardStatus>(
    rec.status === "Completed" ? "applied" : "pending"
  );
  const [error, setError] = useState<string | null>(null);

  const isGoogle = rec.platform === "Google";
  const isMeta = rec.platform === "Meta";
  const qualityLabel = rec.quality_label || (rec.isManualOnly ? "Manual only" : "High confidence");
  const canAutoApply = rec.automation_allowed === true && rec.guardrail_status === "eligible" && !rec.isManualOnly;

  const impactColor = rec.impact === "High"
    ? "bg-red-100 text-red-600"
    : rec.impact === "Medium"
    ? "bg-amber-100 text-amber-700"
    : "bg-green-100 text-green-700";

  const platformColor = isGoogle
    ? "border-l-blue-500"
    : isMeta
    ? "border-l-purple-500"
    : "border-l-teal-500";

  const platformBadgeColor = isGoogle
    ? "bg-blue-50 text-blue-700"
    : isMeta
    ? "bg-purple-50 text-purple-700"
    : "bg-teal-50 text-teal-700";

  // Shared implementation logic (for both Auto and Manual)
  const recordImplementation = async (isManual: boolean, statusOverride?: "Dismissed") => {
    if (!clientName) {
      setError("Client is not configured for this action.");
      return;
    }

    setCardStatus(isManual ? "manual_confirmed" : "applying");
    setError(null);
    try {
      const response = await fetch("/api/tracking", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_name: clientName,
          recommendation_id: rec.id,
          title: rec.title,
          action_type: rec.actionType,
          platform: rec.platform,
          impact: rec.impact,
          suggested_action: rec.suggestedAction,
          target_id: rec.target_id || rec.id, 
          campaign_id: rec.campaign_id,
          adset_id: rec.adset_id,
          keyword: rec.keyword,
          suggested_bid: rec.suggested_bid,
          manual: isManual,
          status: statusOverride,
          baseline_metrics: {
             expected_outcome: rec.expectedImpact || "Improved Performance",
             total_spend: baselineMetrics?.totalSpend,
             total_conversions: baselineMetrics?.totalConversions,
             blended_cpa: baselineMetrics?.blendedCPA,
             blended_roas: baselineMetrics?.blendedROAS,
             spend_delta: baselineMetrics?.spendDelta,
             cpa_delta: baselineMetrics?.cpaDelta,
          },
          normalized_key: rec.normalized_key,
          quality_label: rec.quality_label,
          confidence_score: rec.confidence_score,
          guardrail_status: rec.guardrail_status,
          guardrail_reasons: rec.guardrail_reasons,
          evidence: rec.evidence,
          expected_impact: rec.expectedImpact,
        }),
      });
      
      const result = await response.json();
      if (response.ok) {
        if (result.status === "manual_required") {
          setCardStatus("manual_confirmed");
        } else if (result.status === "dismissed") {
          setCardStatus("dismissed");
        } else if (result.status === "error") {
          setError(result.execution_status || "Execution failed");
          setCardStatus("pending");
        } else {
          setCardStatus("applied");
        }
      } else {
        setError(result.error || "Failed to apply recommendation");
        setCardStatus("pending");
      }
    } catch {
      setError(`Could not record ${isManual ? 'implementation' : 'application'}. Please try again.`);
      setCardStatus("pending");
    }
  };

  // "Apply Now" — calls the tracking endpoint (automated actions)
  const handleApply = () => {
    if (!confirm(`Apply this ${rec.platform} recommendation now? This may change the live ad account.`)) {
      return;
    }
    recordImplementation(false);
  };

  // "Mark as Implemented" — for manual actions
  const handleManualConfirm = () => recordImplementation(true);

  // "Dismiss" — not relevant / already done another way
  const handleDismiss = () => recordImplementation(true, "Dismissed");

  const isDone = cardStatus === "applied" || cardStatus === "manual_confirmed" || cardStatus === "dismissed";

  const actionLabel = ACTION_TYPE_LABELS[rec.actionType] || rec.actionType;
  const bidChangePct = rec.current_bid && rec.suggested_bid
    ? ((rec.suggested_bid - rec.current_bid) / rec.current_bid) * 100
    : null;
  const formatBid = (value: number) => new Intl.NumberFormat("en-MY", {
    style: "currency",
    currency: "MYR",
  }).format(value);
  const primaryActionLabel = rec.actionType === "bid_adjustment" ? "Apply Bid Change" : "Apply Now";

  return (
    <div className={cn(
      "bg-surface shadow-sm rounded-2xl border border-border/40 border-l-4 flex flex-col transition-all",
      platformColor,
      isDone ? "opacity-55 grayscale-[0.3]" : "hover:shadow-md hover:-translate-y-0.5"
    )}>
      {/* ── Header ── */}
      <div className="px-5 pt-5 pb-3">
        <div className="flex items-start gap-2 justify-between mb-3">
          <span className={cn("px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider shrink-0", platformBadgeColor)}>
            {rec.platform}
          </span>
          <div className="flex items-center gap-2 shrink-0">
            <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1", impactColor)}>
              <Zap className="w-3 h-3" /> {rec.impact}
            </span>
          </div>
        </div>

        {/* Action type label */}
        <p className="text-[10px] font-semibold text-text-muted uppercase tracking-widest mb-1.5 flex items-center gap-1">
          <Wrench className="w-3 h-3" /> {actionLabel}
        </p>

        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold",
            QUALITY_STYLES[qualityLabel] || QUALITY_STYLES["Needs review"]
          )}>
            <AlertCircle className="h-3 w-3" />
            {qualityLabel}
            {typeof rec.confidence_score === "number" ? ` - ${Math.round(rec.confidence_score)}%` : ""}
          </span>
        </div>

        {/* Title — clamped, never overflows */}
        <h3 className="text-sm font-bold text-foreground leading-snug line-clamp-3 break-words">
          {rec.title}
        </h3>
      </div>

      {/* ── Detail sections ── */}
      <div className="px-5 pb-4 flex flex-col gap-2.5 flex-1">

        {/* Campaign context */}
        {rec.campaignName && (
          <div className="flex items-start gap-2">
            <Target className="w-3.5 h-3.5 text-text-muted shrink-0 mt-0.5" />
            <p className="text-xs text-text-muted break-words leading-snug">
              <span className="font-semibold text-foreground">Campaign: </span>{rec.campaignName}
            </p>
          </div>
        )}

        {/* Ad Group context */}
        {rec.ad_group_name && rec.ad_group_name !== "Unknown" && (
          <div className="flex items-start gap-2">
            <Layers className="w-3.5 h-3.5 text-text-muted shrink-0 mt-0.5" />
            <p className="text-xs text-text-muted break-words leading-snug">
              <span className="font-semibold text-foreground">Ad Group: </span>{rec.ad_group_name}
            </p>
          </div>
        )}

        {/* Keyword (for negative keyword actions) */}
        {rec.keyword && (
          <div className="bg-surface-hover rounded-lg px-3 py-2">
            <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wide mb-0.5">Keyword</p>
            <p className="text-xs font-medium text-foreground break-all">&ldquo;{rec.keyword}&rdquo;</p>
          </div>
        )}

        {/* Bid change detail */}
        {rec.actionType === "bid_adjustment" && rec.current_bid && rec.suggested_bid && (
          <div className="bg-blue-50 border border-blue-100 rounded-lg px-3 py-2">
            <p className="text-[10px] font-bold text-blue-700 uppercase tracking-wide mb-2">Bid Change</p>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <p className="text-[10px] text-text-muted uppercase font-semibold">Current</p>
                <p className="font-bold text-foreground">{formatBid(rec.current_bid)}</p>
              </div>
              <div>
                <p className="text-[10px] text-text-muted uppercase font-semibold">Suggested</p>
                <p className="font-bold text-blue-700">{formatBid(rec.suggested_bid)}</p>
              </div>
              <div>
                <p className="text-[10px] text-text-muted uppercase font-semibold">Change</p>
                <p className={cn("font-bold", bidChangePct && bidChangePct > 0 ? "text-blue-700" : "text-amber-700")}>
                  {bidChangePct !== null ? `${bidChangePct >= 0 ? "+" : ""}${bidChangePct.toFixed(1)}%` : "-"}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Why — the reason */}
        <div>
          <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wide mb-0.5">Why</p>
          <p className="text-xs text-text-muted leading-relaxed">{rec.description}</p>
        </div>

        {/* What to do */}
        {rec.suggestedAction && (
          <div>
            <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wide mb-0.5">What to do</p>
            <p className="text-xs text-foreground leading-relaxed font-medium">{rec.suggestedAction}</p>
          </div>
        )}

        {/* Expected outcome */}
        {rec.expectedImpact && (
          <div className="bg-green-50 border border-green-100 rounded-lg px-3 py-2 flex items-start gap-2">
            <TrendingUp className="w-3.5 h-3.5 text-green-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-[10px] font-bold text-green-700 uppercase tracking-wide mb-0.5">Expected Outcome</p>
              <p className="text-xs text-green-700 leading-relaxed">{rec.expectedImpact}</p>
            </div>
          </div>
        )}

        {/* Manual-only notice */}
        {(rec.isManualOnly || !canAutoApply) && cardStatus === "pending" && (
          <div className="flex items-start gap-2 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="text-[10px] text-amber-700 leading-snug font-medium">
                This action must be reviewed manually before it changes the ad account.
              </p>
              {(rec.guardrail_reasons || []).slice(0, 2).map((reason) => (
                <p key={reason} className="text-[10px] text-amber-700/80 leading-snug">{reason}</p>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Action buttons ── */}
      <div className="px-5 pb-5">
        {error && <p className="text-[10px] text-red-500 font-bold mb-2">{error}</p>}

        {cardStatus === "applied" && (
          <div className="flex items-center gap-2 bg-green-50 text-green-700 rounded-xl px-4 py-2.5 text-sm font-bold">
            <CheckCircle2 className="w-4 h-4" /> Applied Automatically
          </div>
        )}
        {cardStatus === "manual_confirmed" && (
          <div className="flex items-center gap-2 bg-green-50 text-green-700 rounded-xl px-4 py-2.5 text-sm font-bold">
            <CheckCircle2 className="w-4 h-4" /> Marked as Implemented
          </div>
        )}
        {cardStatus === "dismissed" && (
          <div className="flex items-center gap-2 bg-surface-hover text-text-muted rounded-xl px-4 py-2.5 text-sm font-medium">
            <XCircle className="w-4 h-4" /> Dismissed
          </div>
        )}

        {!isDone && (
          <div className="flex items-center gap-2">
            {/* For manual-only actions: show "Mark as Implemented" as the primary CTA */}
            {!canAutoApply ? (
              <button
                onClick={handleManualConfirm}
                className="flex-1 bg-accent-primary hover:bg-accent-primary/90 text-white text-sm font-semibold py-2.5 px-4 rounded-xl transition-all flex items-center justify-center gap-2 shadow-sm"
              >
                <CheckCircle2 className="w-4 h-4" /> Mark as Implemented
              </button>
            ) : (
              <button
                onClick={handleApply}
                disabled={cardStatus === "applying"}
                className="flex-1 bg-accent-primary hover:bg-accent-primary/90 text-white text-sm font-semibold py-2.5 px-4 rounded-xl transition-all flex items-center justify-center gap-2 shadow-sm disabled:opacity-60"
              >
                {cardStatus === "applying"
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> Applying...</>
                  : primaryActionLabel
                }
              </button>
            )}

            {/* Dismiss button — always available */}
            <button
              onClick={handleDismiss}
              className="p-2.5 rounded-xl bg-surface-hover border border-border/50 text-text-muted hover:text-red-500 hover:border-red-200 transition-colors"
              title="Dismiss this recommendation"
            >
              <XCircle className="w-5 h-5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
