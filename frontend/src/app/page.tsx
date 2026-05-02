"use client";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { UnifiedMetricsCard } from "@/components/ui/UnifiedMetricsCard";
import { DataTable } from "@/components/ui/DataTable";
import { DatePicker } from "@/components/ui/DatePicker";
import React, { useEffect, useState } from "react";
import { DashboardData } from "@/lib/types";
import { mockMetrics, mockRecommendations, mockCampaigns } from "@/lib/mock-data";
import { RefreshCcw } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { DateRangeSelection } from "@/lib/date-range";
import { fetchDashboardData } from "@/lib/dashboard-refresh";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export default function Home() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshingRange, setRefreshingRange] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [platformFilter, setPlatformFilter] = useState<"All" | "Google" | "Meta">("All");

  useEffect(() => {
    async function fetchData() {
      try {
        const jsonData = await fetchDashboardData();
        setData({ ...jsonData, isLive: true });
      } catch (err) {
        const message = err instanceof Error ? err.message : "An error occurred";
        if (message.includes("404")) {
          // Fallback to mock data if live data is still generating
          console.warn("Live data not found, using mock fallback during sync");
          setData({
            metrics: mockMetrics,
            recommendations: mockRecommendations,
            campaigns: mockCampaigns,
            isLive: false,
            client_name: "Mock Client",
            account_name: "Mock Client",
          });
        } else {
          setError(message);
        }
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  async function handleRangeChange(range: DateRangeSelection) {
    if (!data) return;

    setRefreshingRange(true);
    setRefreshError(null);
    const clientName = data.client_name;

    try {
      const nextData = await fetchDashboardData(clientName, range);
      setData({ ...nextData, isLive: true });
      setRefreshError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load dashboard date range.";
      setRefreshError(
        message.includes("(409)")
          ? "This date range is not available in the fast cache yet. It will become available after the scheduled data sync runs."
          : message,
      );
    } finally {
      setRefreshingRange(false);
    }
  }

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex h-[80vh] items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <div className="h-12 w-12 animate-spin rounded-full border-4 border-accent-lime border-t-accent-primary"></div>
            <p className="text-sm font-medium text-text-muted">Connecting to ad accounts...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !data) {
    return (
      <DashboardLayout>
        <div className="flex h-[80vh] items-center justify-center">
          <div className="bg-red-50 text-red-700 p-6 rounded-2xl border border-red-100 max-w-md text-center">
            <h2 className="text-lg font-bold mb-2">Error Loading Dashboard</h2>
            <p className="text-sm mb-4">{error || "Could not retrieve data."}</p>
            <button 
              onClick={() => window.location.reload()}
              className="bg-red-600 text-white px-4 py-2 rounded-xl text-sm font-bold"
            >
              Retry
            </button>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  // Dynamic Filtering Calculations
  const filteredCampaigns = platformFilter === "All" 
    ? data.campaigns 
    : data.campaigns.filter(c => c.platform === platformFilter);

  const dynamicMetrics = platformFilter === "All" ? data.metrics : (() => {
    const totalSpend = filteredCampaigns.reduce((sum, c) => sum + (c.spend || 0), 0);
    const totalConversions = filteredCampaigns.reduce((sum, c) => sum + (c.conversions || 0), 0);
    return {
      totalSpend,
      totalConversions,
      blendedCPA: totalConversions > 0 ? totalSpend / totalConversions : 0,
      blendedROAS: data.metrics.blendedROAS,
      spendDelta: data.metrics.spendDelta, // Keep global deltas for now
      cpaDelta: data.metrics.cpaDelta,
      dateRange: data.metrics.dateRange,
    };
  })();
  const cpaLabel = platformFilter === "All" ? "Blended CPA" : `${platformFilter} CPA`;

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 pb-10">
        
        {/* Page Title (Emitly Style) */}
        <div className="mt-2 mb-2 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold text-foreground tracking-tight">Dashboard</h1>
              {!data.isLive && (
                <span className="flex items-center gap-1.5 bg-accent-lime/20 text-accent-primary px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-tighter border border-accent-lime/50 animate-pulse">
                  <RefreshCcw className="w-3 h-3 animate-spin-slow" />
                  Syncing Live Data
                </span>
              )}
            </div>
            <p className="text-sm font-medium text-text-muted mt-1">
              <strong className="text-foreground font-bold">Welcome back</strong>, here is how your ads are performing today.
            </p>
          </div>
          
          {/* Controls */}
          <div className="flex items-center gap-3">
            {/* Date Picker */}
            <DatePicker
              currentRange={data.date_range}
              loading={refreshingRange}
              onRangeChange={handleRangeChange}
            />

            {/* Platform Toggle */}
            <div className="flex bg-surface border border-border/60 rounded-xl p-1 shadow-sm">
              {(["All", "Google", "Meta"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setPlatformFilter(p)}
                  className={cn(
                    "px-4 py-2 text-sm font-bold rounded-lg transition-colors",
                    platformFilter === p
                      ? "bg-accent-lime text-accent-primary shadow-sm"
                      : "text-text-muted hover:text-foreground"
                  )}
                >
                  {p === "All" ? "Combined" : `${p} Ads`}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Unified Metrics (Emitly Style) */}
        {refreshError && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
            {refreshError}
          </div>
        )}

        <UnifiedMetricsCard metrics={dynamicMetrics} cpaLabel={cpaLabel} />

        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between mb-1">
             <h2 className="text-base font-bold text-foreground">Top Performing Campaigns</h2>
          </div>
          <DataTable data={filteredCampaigns} />
        </div>

      </div>
    </DashboardLayout>
  );
}
