"use client";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import React, { useEffect, useState } from "react";
import { TrendingUp, Clock, CheckCircle2, AlertCircle, Zap, Target, Trash2, Wrench } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface TrackedItem {
  recommendation_id: string;
  client_name: string;
  action_type: string;
  platform: string;
  impact: string;
  title?: string;
  applied_at: string;
  baseline_metrics: {
    expected_outcome: string;
    current_cpa?: number;
    current_spend?: number;
  };
  suggested_action: string;
  status: string;
  days_active: number;
  execution_status?: string;
  quality_label?: string;
  confidence_score?: number;
  expected_impact?: string;
  evidence_snapshot?: {
    spend?: number | null;
    clicks?: number | null;
    conversions?: number | null;
    cpa?: number | null;
  };
  snapshots?: {
    day_0?: unknown;
    day_7?: { summary?: string; actual_impact?: { status?: string } };
    day_14?: { summary?: string; actual_impact?: { status?: string } };
    day_30?: { summary?: string; actual_impact?: { status?: string } };
  };
}

export default function TrackingPage() {
  const [trackedItems, setTrackedItems] = useState<TrackedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchTracking() {
      try {
        const response = await fetch("/api/tracking");
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.error || payload.detail || "Failed to load tracking data");
        }
        const data = await response.json();
        setTrackedItems(data);
      } catch (err) {
        console.error("Failed to load tracking data:", err);
        setError(err instanceof Error ? err.message : "Failed to load tracking data");
      } finally {
        setLoading(false);
      }
    }
    fetchTracking();
  }, []);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex h-[70vh] items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-accent-lime border-t-accent-primary"></div>
            <p className="text-sm font-medium text-text-muted">Loading implementation history...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  // Summary Calculations
  const totalImplemented = trackedItems.length;
  const highImpactCount = trackedItems.filter(i => i.impact === "High").length;
  const googleCount = trackedItems.filter(i => i.platform === "Google").length;
  const metaCount = trackedItems.filter(i => i.platform === "Meta").length;

  if (error) {
    return (
      <DashboardLayout>
        <div className="flex h-[70vh] items-center justify-center">
          <div className="max-w-md rounded-2xl border border-red-100 bg-red-50 p-6 text-center text-red-700">
            <AlertCircle className="mx-auto mb-3 h-8 w-8" />
            <h1 className="mb-2 text-lg font-bold">Tracking Data Error</h1>
            <p className="mb-4 text-sm">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="rounded-xl bg-red-600 px-4 py-2 text-sm font-bold text-white"
            >
              Retry
            </button>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-8 pb-10">
        
        {/* Header */}
        <div className="mt-2">
          <h1 className="text-3xl font-bold text-foreground tracking-tight">Outcome Tracking</h1>
          <p className="text-sm font-medium text-text-muted mt-1">
            Measuring the real-world impact of your AI-driven optimizations.
          </p>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-surface border border-border/40 p-5 rounded-2xl shadow-sm">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-accent-lime/20 rounded-lg text-accent-primary">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <p className="text-xs font-bold text-text-muted uppercase tracking-wider">Total Actions</p>
            </div>
            <p className="text-2xl font-black text-foreground">{totalImplemented}</p>
            <p className="text-[10px] text-text-muted mt-1 font-medium">Applied & Tracking</p>
          </div>

          <div className="bg-surface border border-border/40 p-5 rounded-2xl shadow-sm">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-amber-100 rounded-lg text-amber-600">
                <Zap className="w-5 h-5" />
              </div>
              <p className="text-xs font-bold text-text-muted uppercase tracking-wider">High Impact</p>
            </div>
            <p className="text-2xl font-black text-foreground">{highImpactCount}</p>
            <p className="text-[10px] text-text-muted mt-1 font-medium">Critical optimizations</p>
          </div>

          <div className="bg-surface border border-border/40 p-5 rounded-2xl shadow-sm">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-blue-100 rounded-lg text-blue-600">
                <Target className="w-5 h-5" />
              </div>
              <p className="text-xs font-bold text-text-muted uppercase tracking-wider">Google Ads</p>
            </div>
            <p className="text-2xl font-black text-foreground">{googleCount}</p>
            <p className="text-[10px] text-text-muted mt-1 font-medium">Keywords & Bids</p>
          </div>

          <div className="bg-surface border border-border/40 p-5 rounded-2xl shadow-sm">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-purple-100 rounded-lg text-purple-600">
                <TrendingUp className="w-5 h-5" />
              </div>
              <p className="text-xs font-bold text-text-muted uppercase tracking-wider">Meta Ads</p>
            </div>
            <p className="text-2xl font-black text-foreground">{metaCount}</p>
            <p className="text-[10px] text-text-muted mt-1 font-medium">Creative & Audience</p>
          </div>
        </div>

        {/* Tracking Table */}
        <div className="bg-surface border border-border/40 rounded-3xl overflow-hidden shadow-sm">
          <div className="px-6 py-5 border-b border-border/40 flex items-center justify-between">
            <h2 className="text-base font-bold text-foreground">Implementation History</h2>
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 bg-accent-lime/10 text-accent-primary px-3 py-1 rounded-full text-[10px] font-bold uppercase border border-accent-lime/20">
                <div className="w-1.5 h-1.5 rounded-full bg-accent-lime animate-pulse" />
                Live Monitoring
              </span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-hover/50">
                  <th className="px-6 py-4 text-[10px] font-bold text-text-muted uppercase tracking-widest">Platform</th>
                  <th className="px-6 py-4 text-[10px] font-bold text-text-muted uppercase tracking-widest">Recommendation</th>
                  <th className="px-6 py-4 text-[10px] font-bold text-text-muted uppercase tracking-widest">Applied Date</th>
                  <th className="px-6 py-4 text-[10px] font-bold text-text-muted uppercase tracking-widest">Expected Outcome</th>
                  <th className="px-6 py-4 text-[10px] font-bold text-text-muted uppercase tracking-widest">Status</th>
                  <th className="px-6 py-4 text-[10px] font-bold text-text-muted uppercase tracking-widest">Outcome</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {trackedItems.map((item) => (
                  <tr key={item.recommendation_id} className="hover:bg-surface-hover/30 transition-colors group">
                    <td className="px-6 py-4">
                      <span className={cn(
                        "px-2 py-1 rounded text-[10px] font-bold uppercase",
                        item.platform === "Google" ? "bg-blue-50 text-blue-700" : "bg-purple-50 text-purple-700"
                      )}>
                        {item.platform}
                      </span>
                    </td>
                    <td className="px-6 py-4 max-w-md">
                      <p className="text-sm font-bold text-foreground line-clamp-1">{item.title || item.suggested_action || "Manual Adjustment"}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5">
                        <p className="text-[10px] text-text-muted">{item.action_type}</p>
                        {item.quality_label && (
                          <span className="rounded-full border border-border/50 bg-surface-hover px-2 py-0.5 text-[9px] font-bold uppercase text-text-muted">
                            {item.quality_label}
                            {typeof item.confidence_score === "number" ? ` ${Math.round(item.confidence_score)}%` : ""}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <Clock className="w-3.5 h-3.5 text-text-muted" />
                        <span className="text-xs font-medium text-text-muted">
                          {new Date(item.applied_at).toLocaleDateString()}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col gap-1.5">
                        <div className="flex items-center gap-2">
                          <TrendingUp className="w-3.5 h-3.5 text-green-600" />
                          <span className="text-xs font-bold text-green-700">{item.expected_impact || item.baseline_metrics.expected_outcome || "TBD"}</span>
                        </div>
                        {item.evidence_snapshot && (
                          <p className="text-[10px] text-text-muted">
                            Baseline: {typeof item.evidence_snapshot.spend === "number" ? `RM ${item.evidence_snapshot.spend.toFixed(2)}` : "spend n/a"}
                            {typeof item.evidence_snapshot.conversions === "number" ? `, ${item.evidence_snapshot.conversions} conv.` : ""}
                            {typeof item.evidence_snapshot.cpa === "number" ? `, RM ${item.evidence_snapshot.cpa.toFixed(2)} CPA` : ""}
                          </p>
                        )}
                        {item.execution_status && (
                          <div className={cn(
                            "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-tighter w-fit",
                            item.execution_status.toLowerCase().includes("applied: success") ? "bg-green-50 text-green-700 border border-green-200" :
                            item.execution_status.includes("Manual") ? "bg-amber-50 text-amber-700 border border-amber-200" :
                            item.execution_status.includes("Error") ? "bg-red-50 text-red-700 border border-red-200" :
                            "bg-gray-50 text-gray-700 border border-gray-200"
                          )}>
                            {item.execution_status.toLowerCase().includes("applied: success") ? <CheckCircle2 className="w-2.5 h-2.5" /> : 
                             item.execution_status.includes("Manual") ? <Wrench className="w-2.5 h-2.5" /> :
                             <AlertCircle className="w-2.5 h-2.5" />}
                            {item.execution_status}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={cn(
                        "px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-tighter border",
                        item.status === "Failed" ? "bg-red-50 text-red-700 border-red-200" :
                        item.status === "Dismissed" ? "bg-gray-50 text-gray-600 border-gray-200" :
                        item.status === "Needs data" ? "bg-amber-50 text-amber-700 border-amber-200" :
                        item.status === "Completed" ? "bg-green-50 text-green-700 border-green-200" :
                        "bg-accent-lime/10 text-accent-primary border-accent-lime/20"
                      )}>
                        {item.status === "Dismissed" || item.status === "Failed" || item.status === "Completed" || item.status === "Needs data"
                          ? item.status
                          : `Day ${item.days_active} / 30`
                        }
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-between group">
                        {/* Comparison logic — currently shows "Measuring" if Day 1 */}
                        {item.status === "Dismissed" ? (
                          <span className="text-[10px] font-bold text-text-muted uppercase">Removed from queue</span>
                        ) : item.status === "Failed" ? (
                          <span className="text-[10px] font-bold text-red-600 uppercase">Action failed</span>
                        ) : item.snapshots?.day_30?.summary ? (
                          <span className="text-xs font-bold text-green-700">{item.snapshots.day_30.summary}</span>
                        ) : item.snapshots?.day_14?.summary ? (
                          <span className="text-xs font-bold text-green-700">{item.snapshots.day_14.summary}</span>
                        ) : item.snapshots?.day_7?.summary ? (
                          <span className="text-xs font-bold text-green-700">{item.snapshots.day_7.summary}</span>
                        ) : item.days_active < 7 ? (
                          <div className="flex items-center gap-2">
                             <div className="h-1.5 w-16 bg-border/40 rounded-full overflow-hidden">
                               <div className="h-full bg-accent-lime animate-shimmer" style={{ width: '30%' }} />
                             </div>
                             <span className="text-[10px] font-bold text-text-muted uppercase">Collecting Data</span>
                          </div>
                        ) : (
                          <span className="text-[10px] font-bold text-text-muted uppercase">Awaiting milestone snapshot</span>
                        )}
                        
                        <button 
                          onClick={async () => {
                            if (confirm("Remove this item from tracking?")) {
                              const res = await fetch(`/api/tracking?recommendation_id=${encodeURIComponent(item.recommendation_id)}&client_name=${encodeURIComponent(item.client_name)}`, { method: 'DELETE' });
                              if (res.ok) {
                                setTrackedItems(prev => prev.filter(i => i.recommendation_id !== item.recommendation_id));
                              }
                            }
                          }}
                          className="p-2 text-text-muted hover:text-red-500 transition-colors rounded-lg hover:bg-red-50 opacity-0 group-hover:opacity-100"
                          title="Delete from history"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                
                {trackedItems.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-6 py-20 text-center">
                      <div className="flex flex-col items-center gap-3 opacity-40">
                         <AlertCircle className="w-10 h-10 text-text-muted" />
                         <p className="text-sm font-medium text-text-muted max-w-xs">
                           No implementations recorded yet. Apply your first recommendation to start tracking results.
                         </p>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Legend / Info */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-accent-primary/5 border border-accent-primary/10 p-6 rounded-3xl">
            <h3 className="text-sm font-bold text-accent-primary flex items-center gap-2 mb-3">
              <TrendingUp className="w-4 h-4" /> How Tracking Works
            </h3>
            <ul className="space-y-3">
              <li className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-accent-primary/20 flex items-center justify-center text-[10px] font-bold text-accent-primary shrink-0 mt-0.5">1</div>
                <p className="text-xs text-text-muted leading-relaxed">
                  <strong className="text-foreground">Snapshot</strong>: We capture the baseline CPA, spend, and conversion volume the moment you apply a change.
                </p>
              </li>
              <li className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-accent-primary/20 flex items-center justify-center text-[10px] font-bold text-accent-primary shrink-0 mt-0.5">2</div>
                <p className="text-xs text-text-muted leading-relaxed">
                  <strong className="text-foreground">7-Day Burn</strong>: Advertising algorithms take up to 7 days to stabilize. We display &ldquo;Collecting Data&rdquo; during this period.
                </p>
              </li>
              <li className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-accent-primary/20 flex items-center justify-center text-[10px] font-bold text-accent-primary shrink-0 mt-0.5">3</div>
                <p className="text-xs text-text-muted leading-relaxed">
                  <strong className="text-foreground">Validation</strong>: Performance is compared against the previous 30-day average to calculate the final uplift.
                </p>
              </li>
            </ul>
          </div>
          
          <div className="flex flex-col justify-center items-center p-8 bg-surface border border-border/40 rounded-3xl text-center">
             <div className="w-12 h-12 bg-accent-lime/20 rounded-2xl flex items-center justify-center mb-4">
                <Zap className="w-6 h-6 text-accent-primary" />
             </div>
             <h3 className="text-base font-bold text-foreground mb-2">Continuous Optimization</h3>
             <p className="text-xs text-text-muted max-w-sm leading-relaxed">
               YCK Ads Dashboard uses these historical outcomes to improve its AI impact projections over time, making every recommendation more accurate than the last.
             </p>
          </div>
        </div>

      </div>
    </DashboardLayout>
  );
}
