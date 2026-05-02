"use client";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { RecommendationCard } from "@/components/ui/RecommendationCard";
import React, { useEffect, useState } from "react";
import { DashboardMetrics, Recommendation } from "@/lib/types";

type Filter = "All" | "Google" | "Meta";

type TrackedRecommendation = {
  recommendation_id?: string;
  action_type?: string;
  platform?: string;
  keyword?: string;
  target_id?: string;
  campaign_id?: string;
  normalized_key?: string;
  status?: string;
};

function normalizeMatchValue(value: unknown) {
  return String(value || "")
    .replace(/["']/g, "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function recommendationMatchKey(rec: Recommendation | TrackedRecommendation) {
  const actionType = normalizeMatchValue("actionType" in rec ? rec.actionType : rec.action_type);
  const platform = normalizeMatchValue(rec.platform);
  const keyword = normalizeMatchValue(rec.keyword);
  const target = normalizeMatchValue(
    "ad_group_name" in rec
      ? rec.target_id || rec.ad_group_name
      : rec.target_id,
  );
  const campaign = normalizeMatchValue("campaignName" in rec ? rec.campaign_id || rec.campaignName : rec.campaign_id);

  if (actionType && keyword) return `${platform}|${actionType}|keyword:${keyword}|target:${target}|campaign:${campaign}`;
  if (actionType && target) return `${platform}|${actionType}|target:${target}|campaign:${campaign}`;
  if (actionType && campaign) return `${platform}|${actionType}|campaign:${campaign}`;
  return "";
}

function recommendationFallbackKey(rec: Recommendation | TrackedRecommendation) {
  const actionType = normalizeMatchValue("actionType" in rec ? rec.actionType : rec.action_type);
  const platform = normalizeMatchValue(rec.platform);
  const keyword = normalizeMatchValue(rec.keyword);
  return actionType && keyword ? `${platform}|${actionType}|keyword:${keyword}` : "";
}

function removeTrackedRecommendations(recommendations: Recommendation[], trackedItems: TrackedRecommendation[]) {
  const activeTrackedItems = trackedItems.filter((item) => item.status !== "Failed");
  const trackedIds = new Set(activeTrackedItems.map((item) => item.recommendation_id).filter(Boolean));
  const trackedKeys = new Set(
    activeTrackedItems
      .flatMap((item) => [item.normalized_key, recommendationMatchKey(item), recommendationFallbackKey(item)])
      .filter(Boolean),
  );

  return recommendations.filter((rec) => (
    rec.guardrail_status !== "suppressed" &&
    !trackedIds.has(rec.recommendation_id || rec.id) &&
    !trackedKeys.has(rec.normalized_key || "") &&
    !trackedKeys.has(recommendationMatchKey(rec)) &&
    !trackedKeys.has(recommendationFallbackKey(rec))
  ));
}

export default function RecommendationsPage() {
  const [recommendations, setRecommendations] = useState<Recommendation[] | null>(null);
  const [clientName, setClientName] = useState<string | undefined>();
  const [baselineMetrics, setBaselineMetrics] = useState<DashboardMetrics | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("All");

  useEffect(() => {
    async function fetchData() {
      try {
        const [response, trackingResponse] = await Promise.all([
          fetch("/api/data"),
          fetch("/api/tracking"),
        ]);
        if (!response.ok) throw new Error("Failed to fetch recommendations");
        const data = await response.json();
        const trackedItems = trackingResponse.ok ? await trackingResponse.json() : [];
        setRecommendations(removeTrackedRecommendations(data.recommendations || [], trackedItems));
        setClientName(data.client_name);
        setBaselineMetrics(data.metrics);
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex h-[60vh] items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-accent-lime border-t-accent-primary"></div>
            <p className="text-sm font-medium text-text-muted">Analyzing your ad performance...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const allRecs = recommendations || [];
  const filtered = filter === "All" ? allRecs : allRecs.filter(r => r.platform === filter);
  const googleCount = allRecs.filter(r => r.platform === "Google").length;
  const metaCount = allRecs.filter(r => r.platform === "Meta").length;

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 pb-10">
        
        {/* Header + toggle */}
        <div className="mt-2 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">Recommendations Engine</h1>
            <p className="text-sm font-medium text-text-muted mt-1">AI-driven actionable insights across your ad accounts.</p>
          </div>

          {/* Platform Filter Toggle */}
          <div className="flex bg-surface border border-border/60 rounded-xl p-1 shadow-sm shrink-0">
            {(["All", "Google", "Meta"] as Filter[]).map(p => (
              <button
                key={p}
                onClick={() => setFilter(p)}
                className={[
                  "px-4 py-2 text-sm font-bold rounded-lg transition-colors flex items-center gap-2",
                  filter === p
                    ? "bg-accent-lime text-accent-primary shadow-sm"
                    : "text-text-muted hover:text-foreground"
                ].join(" ")}
              >
                {p === "All" ? `All (${allRecs.length})` : p === "Google" ? `Google (${googleCount})` : `Meta (${metaCount})`}
              </button>
            ))}
          </div>
        </div>

        {error ? (
          <div className="bg-red-50 text-red-700 p-6 rounded-2xl border border-red-100 text-center">
            <p className="text-sm">{error}</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filtered.map((rec) => (
                <RecommendationCard
                  key={rec.id}
                  recommendation={rec}
                  clientName={clientName}
                  baselineMetrics={baselineMetrics}
                />
              ))}
              {filtered.length === 0 && (
                <div className="col-span-full py-20 text-center border-2 border-dashed border-border rounded-3xl">
                  <p className="text-text-muted font-medium">No {filter === "All" ? "" : filter + " "}recommendations available right now.</p>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
