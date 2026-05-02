"use client";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { DatePicker } from "@/components/ui/DatePicker";
import { DateRangeSelection } from "@/lib/date-range";
import { fetchDashboardData } from "@/lib/dashboard-refresh";
import React, { useEffect, useState } from "react";

// ─── helpers ────────────────────────────────────────────────────────────────
function fmt(n: number, decimals = 0) {
  return n.toLocaleString("en-MY", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
function fmtMYR(n: number) {
  return new Intl.NumberFormat("en-MY", { style: "currency", currency: "MYR" }).format(n);
}
function fmtPct(n: number) {
  return `${n.toFixed(2)}%`;
}
function isTrendValue(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

// ─── shared components ───────────────────────────────────────────────────────
function SectionCard({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="bg-surface shadow-sm rounded-2xl border border-border/60 overflow-hidden">
      <div className="px-6 py-4 border-b border-border/60">
        <h2 className="text-base font-bold text-foreground">{title}</h2>
        {description && <p className="text-xs text-text-muted mt-0.5">{description}</p>}
      </div>
      <div className="overflow-x-auto">{children}</div>
    </div>
  );
}

type TableRow = Record<string, any>;

function DetailTable({ headers, rows }: {
  headers: { label: string; key: string; align?: "left" | "right"; render?: (v: any, row: TableRow) => React.ReactNode }[];
  rows: TableRow[];
}) {
  if (!rows.length) return <p className="p-6 text-sm text-text-muted italic">No data available.</p>;
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b border-border/60">
          {headers.map(h => (
            <th key={h.key} className={`px-4 py-3 font-semibold text-text-muted uppercase tracking-wide bg-surface-hover ${h.align === "right" ? "text-right" : "text-left"}`}>
              {h.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="border-b border-border/40 hover:bg-surface-hover/50 transition-colors">
            {headers.map(h => (
              <td key={h.key} className={`px-4 py-3 ${h.align === "right" ? "text-right tabular-nums" : ""}`}>
                {h.render ? h.render(row[h.key], row) : row[h.key] ?? "—"}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function KpiStrip({ items }: { items: { label: string; value: string; sub?: string; highlight?: "good" | "warn" | "bad" }[] }) {
  const colorMap = { good: "text-green-600", warn: "text-amber-600", bad: "text-red-500" };
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {items.map((item, i) => (
        <div key={i} className="bg-surface rounded-2xl border border-border/60 p-4 text-center">
          <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wide mb-1">{item.label}</p>
          <p className={`text-xl font-bold ${item.highlight ? colorMap[item.highlight] : "text-foreground"}`}>{item.value}</p>
          {item.sub && <p className="text-[10px] text-text-muted mt-0.5">{item.sub}</p>}
        </div>
      ))}
    </div>
  );
}

function InsightCard({ insight }: { insight: any }) {
  const colorMap: Record<string, string> = {
    warning: "border-l-amber-500 bg-amber-50",
    success: "border-l-green-500 bg-green-50",
    info: "border-l-blue-500 bg-blue-50",
    critical: "border-l-red-500 bg-red-50",
  };
  return (
    <div className={`border-l-4 rounded-r-xl p-4 ${colorMap[insight.type] || colorMap.info}`}>
      <p className="text-sm font-bold text-foreground mb-1">{insight.title}</p>
      <p className="text-xs text-text-muted leading-relaxed">{insight.description}</p>
    </div>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────
export default function GoogleAdsPage() {
  const [d, setD] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshingRange, setRefreshingRange] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboardData()
      .then(json => { setD(json); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  async function handleRangeChange(range: DateRangeSelection) {
    if (!d) return;

    setRefreshingRange(true);
    setRefreshError(null);
    const clientName = d.client_name;

    try {
      const nextData = await fetchDashboardData(clientName, range);
      setD(nextData);
      setRefreshError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load Google Ads date range.";
      setRefreshError(
        message.includes("(409)")
          ? "This date range is not available in the fast cache yet. It will become available after the scheduled data sync runs."
          : message,
      );
    } finally {
      setRefreshingRange(false);
    }
  }

  if (loading) return (
    <DashboardLayout>
      <div className="flex h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-accent-lime border-t-accent-primary" />
          <p className="text-sm text-text-muted">Loading Google Ads data...</p>
        </div>
      </div>
    </DashboardLayout>
  );

  if (error || !d) return (
    <DashboardLayout>
      <div className="flex h-[60vh] items-center justify-center">
        <div className="bg-red-50 text-red-700 p-6 rounded-2xl border border-red-100 text-center max-w-md">
          <p className="text-sm">{error || "Could not load data."}</p>
          <button onClick={() => window.location.reload()} className="mt-4 bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-bold">Retry</button>
        </div>
      </div>
    </DashboardLayout>
  );

  const googleCampaigns = (d.campaigns || []).filter((c: any) => c.platform === "Google");
  const searchQueries: any[] = d.search_queries || [];
  const geoGoogle: any[] = d.geo_performance || [];
  const keywords: any[] = d.keywords || [];
  const insights: any[] = d.insights || [];
  const recommendations: any[] = (d.recommendations || []).filter((r: any) => r.platform !== "Meta");
  const trends = d.trends || {};
  const trendItems = [
    { label: "Spend Change", key: "spend_change" },
    { label: "Conversions Change", key: "conversions_change" },
    { label: "CPA Change", key: "cpa_change" },
    { label: "Quality Score Change", key: "quality_score_change" },
  ].filter(t => isTrendValue(trends[t.key]));

  const gSpend = googleCampaigns.reduce((s: number, c: any) => s + (c.spend || 0), 0);
  const gConversions = googleCampaigns.reduce((s: number, c: any) => s + (c.conversions || 0), 0);
  const gCPA = gConversions > 0 ? gSpend / gConversions : 0;
  const gClicks = googleCampaigns.reduce((s: number, c: any) => s + (c.clicks || 0), 0);
  const gImpressions = googleCampaigns.reduce((s: number, c: any) => s + (c.impressions || 0), 0);
  const avgQS = keywords.length > 0
    ? keywords.filter((k: any) => k.quality_score).reduce((s: number, k: any) => s + k.quality_score, 0) / keywords.filter((k: any) => k.quality_score).length
    : null;

  // Performers
  const topPerformers = [...googleCampaigns].filter((c: any) => c.conversions > 0).sort((a, b) => a.cpa - b.cpa).slice(0, 3);
  const underperformers = [...googleCampaigns].filter((c: any) => c.spend > 10 && c.conversions === 0).sort((a, b) => b.spend - a.spend).slice(0, 3);

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 pb-10">

        {/* Header */}
        <div className="mt-2 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">Google Ads</h1>
            <p className="text-sm text-text-muted mt-1">
              Search &amp; display performance for <strong className="text-foreground">{d.account_name || d.client_name || "Selected client"}</strong>
              {d.date_range ? ` · ${d.date_range.start_date || ""} to ${d.date_range.end_date || ""}` : ""}
            </p>
          </div>
          <DatePicker
            currentRange={d.date_range}
            loading={refreshingRange}
            onRangeChange={handleRangeChange}
          />
        </div>

        {refreshError && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
            {refreshError}
          </div>
        )}

        {/* ── KPI Strip ── */}
        <KpiStrip items={[
          { label: "Total Spend", value: fmtMYR(gSpend) },
          { label: "Conversions", value: fmt(gConversions), sub: `CPA: ${fmtMYR(gCPA)}` },
          { label: "Clicks", value: fmt(gClicks), sub: `CPC: ${fmtMYR(gClicks > 0 ? gSpend / gClicks : 0)}` },
          { label: "Impressions", value: fmt(gImpressions) },
          { label: "CTR", value: fmtPct(gImpressions > 0 ? (gClicks / gImpressions) * 100 : 0) },
          { label: "Avg Quality Score", value: avgQS ? avgQS.toFixed(1) : "—", highlight: avgQS && avgQS >= 7 ? "good" : avgQS && avgQS >= 5 ? "warn" : "bad" },
        ]} />

        {/* ── Trends ── */}
        {trendItems.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {trendItems.map(t => (
              <div key={t.key} className="bg-surface rounded-2xl border border-border/60 p-4 text-center">
                <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wide mb-1">{t.label}</p>
                <p className={`text-lg font-bold ${trends[t.key] > 0 ? "text-green-600" : trends[t.key] < 0 ? "text-red-500" : "text-foreground"}`}>
                  {trends[t.key] > 0 ? "+" : ""}{trends[t.key].toFixed(1)}%
                </p>
              </div>
            ))}
          </div>
        )}

        {/* ── AI Insights ── */}
        {insights.length > 0 && (
          <SectionCard title="AI Insights Summary">
            <div className="flex flex-col gap-3 p-4">
              {insights.map((ins: any, i: number) => <InsightCard key={i} insight={ins} />)}
            </div>
          </SectionCard>
        )}

        {/* ── Top Performers & Issues ── */}
        {(topPerformers.length > 0 || underperformers.length > 0) && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {topPerformers.length > 0 && (
              <SectionCard title="Top Performers">
                <DetailTable
                  headers={[
                    { label: "Campaign", key: "name" },
                    { label: "Conv", key: "conversions", align: "right", render: (v) => fmt(v) },
                    { label: "Spend", key: "spend", align: "right", render: (v) => fmtMYR(v) },
                    { label: "CPA", key: "cpa", align: "right", render: (v) => <span className="font-semibold text-green-600">{fmtMYR(v)}</span> },
                  ]}
                  rows={topPerformers}
                />
              </SectionCard>
            )}
            {underperformers.length > 0 && (
              <SectionCard title="Issues & Underperformers" description="High spend, zero conversions.">
                <DetailTable
                  headers={[
                    { label: "Campaign", key: "name" },
                    { label: "Spend", key: "spend", align: "right", render: (v) => <span className="font-semibold text-red-500">{fmtMYR(v)}</span> },
                    { label: "Clicks", key: "clicks", align: "right", render: (v) => fmt(v) },
                    { label: "Conv", key: "conversions", align: "right", render: (v) => <span className="text-red-500 font-bold">{v}</span> },
                  ]}
                  rows={underperformers}
                />
              </SectionCard>
            )}
          </div>
        )}

        {/* ── Campaign Performance ── */}
        <SectionCard title="Campaign Performance">
          <DetailTable
            headers={[
              { label: "Campaign", key: "name" },
              { label: "Status", key: "status", render: (v) => <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${v === "Active" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>{v}</span> },
              { label: "Spend", key: "spend", align: "right", render: (v) => fmtMYR(v) },
              { label: "Impr.", key: "impressions", align: "right", render: (v) => fmt(v) },
              { label: "Clicks", key: "clicks", align: "right", render: (v) => fmt(v) },
              { label: "CTR", key: "ctr", align: "right", render: (v) => v ? fmtPct(v * 100) : "—" },
              { label: "Conv", key: "conversions", align: "right", render: (v) => fmt(v) },
              { label: "CPA", key: "cpa", align: "right", render: (v) => v > 0 ? fmtMYR(v) : <span className="text-text-muted">—</span> },
            ]}
            rows={googleCampaigns}
          />
        </SectionCard>

        {/* ── Keywords ── */}
        {keywords.length > 0 && (
          <SectionCard title={`Keywords (${keywords.length})`} description="Keyword-level performance including Quality Scores.">
            <DetailTable
              headers={[
                { label: "Keyword", key: "keyword" },
                { label: "Campaign", key: "campaign" },
                { label: "Impr.", key: "impressions", align: "right", render: (v) => fmt(v) },
                { label: "Clicks", key: "clicks", align: "right", render: (v) => fmt(v) },
                { label: "CTR", key: "ctr", align: "right", render: (v) => fmtPct(v * 100) },
                { label: "Avg CPC", key: "avg_cpc", align: "right", render: (v) => fmtMYR(v) },
                { label: "QS", key: "quality_score", align: "right", render: (v) => v != null
                  ? <span className={`font-bold ${v >= 7 ? "text-green-600" : v >= 5 ? "text-amber-600" : "text-red-500"}`}>{v}/10</span>
                  : <span className="text-text-muted">—</span>
                },
              ]}
              rows={keywords}
            />
          </SectionCard>
        )}

        {/* ── Search Query Performance ── */}
        {searchQueries.length > 0 && (
          <SectionCard title={`Search Query Report (${searchQueries.length} queries)`} description="Actual search terms that triggered your ads.">
            <DetailTable
              headers={[
                { label: "Search Query", key: "query" },
                { label: "Campaign", key: "campaign" },
                { label: "Impr.", key: "impressions", align: "right", render: (v) => fmt(v) },
                { label: "Clicks", key: "clicks", align: "right", render: (v) => fmt(v) },
                { label: "CTR", key: "ctr", align: "right", render: (v) => fmtPct(v * 100) },
                { label: "Cost", key: "cost", align: "right", render: (v) => fmtMYR(v) },
                { label: "Conv", key: "conversions", align: "right", render: (v) => fmt(v) },
                { label: "CPA", key: "cpa", align: "right", render: (v, row) => row.conversions > 0 ? fmtMYR(v) : <span className="text-text-muted">—</span> },
              ]}
              rows={searchQueries}
            />
          </SectionCard>
        )}

        {/* ── Geographic Performance ── */}
        {geoGoogle.length > 0 && (
          <SectionCard title="Geographic Performance" description="Performance by location targeting radius.">
            <DetailTable
              headers={[
                { label: "Location", key: "location_name" },
                { label: "Campaign", key: "campaign_name" },
                { label: "Impr.", key: "impressions", align: "right", render: (v) => fmt(v) },
                { label: "Clicks", key: "clicks", align: "right", render: (v) => fmt(v) },
                { label: "CTR", key: "ctr", align: "right", render: (v) => fmtPct(v * 100) },
                { label: "Cost", key: "cost", align: "right", render: (v) => fmtMYR(v) },
                { label: "Conv", key: "conversions", align: "right", render: (v) => fmt(v) },
              ]}
              rows={geoGoogle}
            />
          </SectionCard>
        )}

        {/* ── Recommendations ── */}
        {recommendations.length > 0 && (
          <SectionCard title={`Optimization Recommendations (${recommendations.length})`} description="Actionable recommendations. Apply these to improve performance.">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4">
              {recommendations.map((rec: any, i: number) => (
                <div key={i} className="border border-border/60 rounded-xl p-4 hover:shadow-sm transition-shadow">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-bold text-foreground">{rec.title}</p>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      rec.impact === "High" ? "bg-red-100 text-red-600" :
                      rec.impact === "Medium" ? "bg-amber-100 text-amber-700" : "bg-green-100 text-green-700"
                    }`}>{rec.impact}</span>
                  </div>
                  <p className="text-xs text-text-muted leading-relaxed">{rec.description}</p>
                </div>
              ))}
            </div>
          </SectionCard>
        )}

      </div>
    </DashboardLayout>
  );
}
