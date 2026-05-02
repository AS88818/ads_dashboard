"use client";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { DatePicker } from "@/components/ui/DatePicker";
import { DateRangeSelection } from "@/lib/date-range";
import { fetchDashboardData } from "@/lib/dashboard-refresh";
import React, { useEffect, useState } from "react";

// ─── helpers ────────────────────────────────────────────────────────────────
function fmt(n: number, decimals = 0) {
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-MY", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
function fmtMYR(n: number) {
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-MY", { style: "currency", currency: "MYR" }).format(n);
}
function fmtPct(n: number) {
  if (!Number.isFinite(n)) return "—";
  return `${n.toFixed(2)}%`;
}

function metricNumber(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function cpaFor(row: any) {
  const explicit = Number(row.cost_per_conversion ?? row.cpa);
  if (Number.isFinite(explicit) && explicit > 0) return explicit;

  const spend = metricNumber(row.spend);
  const conversions = metricNumber(row.conversions);
  return conversions > 0 ? spend / conversions : 0;
}

const weekdayOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function weekdayFromDate(dateValue: unknown) {
  if (typeof dateValue !== "string") return null;
  const match = dateValue.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return weekdayOrder[(date.getUTCDay() + 6) % 7];
}

function buildDayOfWeekRows(rows: any[]) {
  const grouped = new Map<string, { day: string; clicks: number; spend: number; conversions: number; cpa: number }>();

  for (const day of weekdayOrder) {
    grouped.set(day, { day, clicks: 0, spend: 0, conversions: 0, cpa: 0 });
  }

  for (const row of rows) {
    const day = row.day_of_week || row.day || weekdayFromDate(row.date);
    if (!day || !grouped.has(day)) continue;

    const item = grouped.get(day)!;
    item.clicks += metricNumber(row.clicks);
    item.spend += metricNumber(row.spend);
    item.conversions += metricNumber(row.conversions);
  }

  return weekdayOrder.map((day) => {
    const item = grouped.get(day)!;
    return {
      ...item,
      cpa: item.conversions > 0 ? item.spend / item.conversions : 0,
    };
  });
}

// ─── sub-components ─────────────────────────────────────────────────────────
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

function MetricBadge({ value, good }: { value: string; good?: boolean | null }) {
  if (good === null || good === undefined) return <span className="font-medium">{value}</span>;
  return (
    <span className={`font-semibold ${good ? "text-green-600" : "text-red-500"}`}>{value}</span>
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

function KpiStrip({ items }: { items: { label: string; value: string; sub?: string; color?: string }[] }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
      {items.map((item, i) => (
        <div key={i} className="bg-surface rounded-2xl border border-border/60 p-4 text-center">
          <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wide mb-1">{item.label}</p>
          <p className={`text-xl font-bold ${item.color || "text-foreground"}`}>{item.value}</p>
          {item.sub && <p className="text-[10px] text-text-muted mt-0.5">{item.sub}</p>}
        </div>
      ))}
    </div>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────
function InsightCard({ insight }: { insight: { type: string; title: string; description: string } }) {
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

function buildMetaInsights({
  campaigns,
  placements,
  demographics,
  hourly,
  daily,
  spend,
  conversions,
  cpa,
}: {
  campaigns: any[];
  placements: any[];
  demographics: any[];
  hourly: any[];
  daily: any[];
  spend: number;
  conversions: number;
  cpa: number;
}) {
  const insights: { type: string; title: string; description: string }[] = [];
  const activeCampaigns = campaigns.filter((c: any) => c.status === "Active" || c.status === "ACTIVE");
  const campaignsWithConversions = campaigns.filter((c: any) => (c.conversions || 0) > 0);
  const zeroConversionSpend = campaigns
    .filter((c: any) => (c.spend || 0) > 0 && (c.conversions || 0) === 0)
    .reduce((sum: number, c: any) => sum + (c.spend || 0), 0);

  if (spend > 0) {
    insights.push({
      type: conversions > 0 ? "success" : "critical",
      title: conversions > 0 ? "Meta Acquisition Summary" : "Meta Conversion Tracking Alert",
      description: conversions > 0
        ? `${fmtMYR(spend)} generated ${fmt(conversions)} Meta conversions at ${fmtMYR(cpa)} CPA.`
        : `${fmtMYR(spend)} spent with no Meta conversions recorded. Check event tracking, campaign objectives, and lead attribution.`,
    });
  }

  if (campaignsWithConversions.length > 0) {
    const bestCampaign = [...campaignsWithConversions].sort((a: any, b: any) => (a.cpa || Infinity) - (b.cpa || Infinity))[0];
    insights.push({
      type: "success",
      title: `Best Meta Campaign: ${bestCampaign.name || bestCampaign.campaign_name}`,
      description: `${fmt(bestCampaign.conversions || 0)} conversions from ${fmtMYR(bestCampaign.spend || 0)} spend at ${fmtMYR(bestCampaign.cpa || 0)} CPA.`,
    });
  }

  if (zeroConversionSpend > 0) {
    const worstCampaign = [...campaigns]
      .filter((c: any) => (c.spend || 0) > 0 && (c.conversions || 0) === 0)
      .sort((a: any, b: any) => (b.spend || 0) - (a.spend || 0))[0];
    insights.push({
      type: "warning",
      title: "Spend Without Conversions",
      description: `${fmtMYR(zeroConversionSpend)} was spent on Meta campaigns with zero conversions. Highest contributor: ${worstCampaign?.name || worstCampaign?.campaign_name || "unknown campaign"}.`,
    });
  }

  const placementWithConversions = placements.filter((p: any) => (p.conversions || 0) > 0);
  if (placementWithConversions.length > 0) {
    const bestPlacement = [...placementWithConversions].sort((a: any, b: any) => (a.cpa || Infinity) - (b.cpa || Infinity))[0];
    insights.push({
      type: "info",
      title: `Best Placement: ${bestPlacement.placement_name}`,
      description: `${fmt(bestPlacement.conversions || 0)} conversions at ${fmtMYR(bestPlacement.cpa || 0)} CPA. Consider shifting budget toward placements with proven conversion volume.`,
    });
  }

  const demographicWithConversions = demographics.filter((d: any) => (d.conversions || 0) > 0);
  if (demographicWithConversions.length > 0) {
    const bestAudience = [...demographicWithConversions].sort((a: any, b: any) => (a.cpa || Infinity) - (b.cpa || Infinity))[0];
    insights.push({
      type: "info",
      title: `Best Audience Segment: ${bestAudience.age || "Unknown age"} ${bestAudience.gender || ""}`.trim(),
      description: `${fmt(bestAudience.conversions || 0)} conversions from ${fmtMYR(bestAudience.spend || 0)} spend at ${fmtMYR(bestAudience.cpa || 0)} CPA.`,
    });
  }

  if (hourly.length > 0) {
    const bestHour = [...hourly]
      .filter((h: any) => (h.conversions || 0) > 0)
      .sort((a: any, b: any) => cpaFor(a) - cpaFor(b))[0];
    if (bestHour) {
      const hourLabel = `${String(bestHour.hour ?? bestHour.hour_of_day ?? "").padStart(2, "0")}:00`;
      insights.push({
        type: "info",
        title: `Best Performing Hour: ${hourLabel}`,
        description: `${hourLabel} generated ${fmt(bestHour.conversions || 0)} conversions at ${fmtMYR(cpaFor(bestHour))} CPA.`,
      });
    }
  }

  if (daily.length > 0) {
    const bestDay = [...daily]
      .filter((day: any) => (day.conversions || 0) > 0)
      .sort((a: any, b: any) => cpaFor(a) - cpaFor(b))[0];
    if (bestDay) {
      insights.push({
        type: "info",
        title: `Best Performing Day: ${bestDay.day_of_week || bestDay.day || bestDay.date || "Unknown"}`,
        description: `${fmt(bestDay.conversions || 0)} conversions at ${fmtMYR(cpaFor(bestDay))} CPA.`,
      });
    }
  }

  const highFrequencyCampaign = campaigns
    .filter((c: any) => (c.frequency || 0) >= 3)
    .sort((a: any, b: any) => (b.frequency || 0) - (a.frequency || 0))[0];
  if (highFrequencyCampaign) {
    insights.push({
      type: "warning",
      title: "Frequency Watch",
      description: `${highFrequencyCampaign.name || highFrequencyCampaign.campaign_name} has ${Number(highFrequencyCampaign.frequency || 0).toFixed(1)} frequency. Watch for creative fatigue if CPA starts rising.`,
    });
  }

  if (activeCampaigns.length > 0) {
    insights.push({
      type: "info",
      title: "Campaign Status",
      description: `${activeCampaigns.length} Meta campaigns are active out of ${campaigns.length} total campaigns in this date range.`,
    });
  }

  return insights.slice(0, 6);
}

export default function MetaAdsPage() {
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
      const message = err instanceof Error ? err.message : "Failed to load Meta Ads date range.";
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
          <p className="text-sm text-text-muted">Loading Meta Ads data...</p>
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

  const metaCampaigns = (d.campaigns || []).filter((c: any) => c.platform === "Meta");
  const adSets: any[] = d.ad_sets || [];
  const demographics: any[] = d.demographic_breakdown || [];
  const placements: any[] = d.placement_breakdown || [];
  const geoMeta: any[] = d.meta_geo_performance || [];
  const timePerf = d.time_performance || {};
  const hourly: any[] = timePerf.hourly || [];
  const daily: any[] = timePerf.daily || [];
  const dayOfWeekRows = buildDayOfWeekRows(daily);
  const recommendations: any[] = (d.recommendations || []).filter((r: any) => r.platform === "Meta");

  // Derived summary from Meta campaigns only
  const metaSpend = metaCampaigns.reduce((s: number, c: any) => s + (c.spend || 0), 0);
  const metaConversions = metaCampaigns.reduce((s: number, c: any) => s + (c.conversions || 0), 0);
  const metaCPA = metaConversions > 0 ? metaSpend / metaConversions : 0;
  const metaClicks = metaCampaigns.reduce((s: number, c: any) => s + (c.clicks || 0), 0);
  const metaImpressions = metaCampaigns.reduce((s: number, c: any) => s + (c.impressions || 0), 0);
  const bestPlacement = placements.length > 0
    ? placements.reduce((best: any, p: any) => (!best || (p.conversions || 0) > (best.conversions || 0)) ? p : best, null)
    : null;
  const metaInsights = buildMetaInsights({
    campaigns: metaCampaigns,
    placements,
    demographics,
    hourly,
    daily: dayOfWeekRows,
    spend: metaSpend,
    conversions: metaConversions,
    cpa: metaCPA,
  });

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 pb-10">

        {/* Header */}
        <div className="mt-2 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">Meta Ads</h1>
            <p className="text-sm text-text-muted mt-1">
              Facebook &amp; Instagram campaign performance for <strong className="text-foreground">{d.account_name || d.client_name || "Selected client"}</strong>
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

        {/* ── Top KPIs ── */}
        <KpiStrip items={[
          { label: "Total Spend", value: fmtMYR(metaSpend) },
          { label: "Conversions", value: fmt(metaConversions), sub: `CPA: ${fmtMYR(metaCPA)}` },
          { label: "Clicks", value: fmt(metaClicks), sub: `CPC: ${fmtMYR(metaClicks > 0 ? metaSpend / metaClicks : 0)}` },
          { label: "Impressions", value: fmt(metaImpressions) },
          { label: "CTR", value: fmtPct(metaImpressions > 0 ? (metaClicks / metaImpressions) * 100 : 0) },
          { label: "CPM", value: fmtMYR(metaImpressions > 0 ? (metaSpend / metaImpressions) * 1000 : 0), sub: "per 1,000 impr." },
          { label: "Best Placement", value: bestPlacement ? bestPlacement.placement_name.split(" - ")[1] || bestPlacement.placement_name : "—", sub: bestPlacement ? `CPA ${fmtMYR(bestPlacement.cpa)}` : undefined },
        ]} />

        {/* ── AI Insights ── */}
        {metaInsights.length > 0 && (
          <SectionCard title="AI Insights Summary">
            <div className="flex flex-col gap-3 p-4">
              {metaInsights.map((insight, i) => (
                <InsightCard key={i} insight={insight} />
              ))}
            </div>
          </SectionCard>
        )}

        {recommendations.length > 0 && (
          <SectionCard title={`Optimization Recommendations (${recommendations.length})`} description="Actionable insights sorted by priority. Apply these to improve performance.">
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

        {/* ── Campaign Performance ── */}
        <SectionCard title="Campaign Performance">
          <DetailTable
            headers={[
              { label: "Campaign", key: "name" },
              { label: "Status", key: "status", render: (v) => <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${v === "Active" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>{v}</span> },
              { label: "Objective", key: "objective" },
              { label: "Spend", key: "spend", align: "right", render: (v) => <span className="font-medium">{fmtMYR(v)}</span> },
              { label: "Reach", key: "impressions", align: "right", render: (v) => fmt(v) },
              { label: "Freq", key: "frequency", align: "right", render: (v) => v ? v.toFixed(1) : "—" },
              { label: "Clicks", key: "clicks", align: "right", render: (v) => fmt(v) },
              { label: "CTR", key: "ctr", align: "right", render: (v) => v ? fmtPct(v) : "—" },
              { label: "Conv", key: "conversions", align: "right", render: (v) => fmt(v) },
              { label: "CPA", key: "cpa", align: "right", render: (v) => <MetricBadge value={fmtMYR(v)} good={v > 0 && v < 5 ? true : v === 0 ? null : false} /> },
            ]}
            rows={metaCampaigns}
          />
        </SectionCard>

        {/* ── Ad Set Performance ── */}
        {adSets.length > 0 && (
          <SectionCard title="Ad Set Performance" description="Ad sets with targeting and performance metrics.">
            <DetailTable
              headers={[
                { label: "Ad Set", key: "adset_name" },
                { label: "Campaign", key: "campaign_name" },
                { label: "Goal", key: "optimization_goal" },
                { label: "Spend", key: "spend", align: "right", render: (v) => fmtMYR(v) },
                { label: "Clicks", key: "clicks", align: "right", render: (v) => fmt(v) },
                { label: "CTR", key: "ctr", align: "right", render: (v) => fmtPct(v) },
                { label: "Conv", key: "conversions", align: "right", render: (v) => fmt(v) },
                { label: "CPA", key: "cpa", align: "right", render: (v) => fmtMYR(v) },
                { label: "Status", key: "status", render: (v) => <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${v === "ACTIVE" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>{v}</span> },
              ]}
              rows={adSets}
            />
          </SectionCard>
        )}

        {/* ── Placement Performance ── */}
        {placements.length > 0 && (
          <SectionCard title="Placement Performance" description="Performance across Facebook, Instagram, Audience Network, and Messenger.">
            <DetailTable
              headers={[
                { label: "Placement", key: "placement_name" },
                { label: "Spend", key: "spend", align: "right", render: (v) => fmtMYR(v) },
                { label: "Clicks", key: "clicks", align: "right", render: (v) => fmt(v) },
                { label: "CTR", key: "ctr", align: "right", render: (v) => fmtPct(v) },
                { label: "CPM", key: "cpm", align: "right", render: (v) => fmtMYR(v) },
                { label: "Conv", key: "conversions", align: "right", render: (v) => fmt(v) },
                { label: "CPA", key: "cpa", align: "right", render: (v) => <MetricBadge value={fmtMYR(v)} good={v > 0 && v < 5 ? true : v === 0 ? null : false} /> },
              ]}
              rows={placements}
            />
          </SectionCard>
        )}

        {/* ── Demographic Performance ── */}
        {demographics.length > 0 && (
          <SectionCard title="Demographic Performance" description="Spend and conversions by age and gender.">
            <DetailTable
              headers={[
                { label: "Age", key: "age" },
                { label: "Gender", key: "gender", render: (v) => <span className="capitalize">{v}</span> },
                { label: "Impressions", key: "impressions", align: "right", render: (v) => fmt(v) },
                { label: "Clicks", key: "clicks", align: "right", render: (v) => fmt(v) },
                { label: "CTR", key: "ctr", align: "right", render: (v) => fmtPct(v) },
                { label: "Spend", key: "spend", align: "right", render: (v) => fmtMYR(v) },
                { label: "Conv", key: "conversions", align: "right", render: (v) => fmt(v) },
                { label: "CPA", key: "cpa", align: "right", render: (v, row) => row.conversions > 0 ? <MetricBadge value={fmtMYR(v)} good={v > 0 && v < 5} /> : <span className="text-text-muted">—</span> },
              ]}
              rows={demographics}
            />
          </SectionCard>
        )}

        {/* ── Geographic Performance ── */}
        {geoMeta.length > 0 && (
          <SectionCard title="Geographic Performance">
            <DetailTable
              headers={[
                { label: "Location", key: "location_name" },
                { label: "Clicks", key: "clicks", align: "right", render: (v) => fmt(v) },
                { label: "Spend", key: "spend", align: "right", render: (v) => fmtMYR(v) },
                { label: "Conv", key: "conversions", align: "right", render: (v) => fmt(v) },
                { label: "CPA", key: "cpa", align: "right", render: (v, row) => row.conversions > 0 ? fmtMYR(v) : <span className="text-text-muted">—</span> },
                { label: "CTR", key: "ctr", align: "right", render: (v) => fmtPct(v) },
              ]}
              rows={geoMeta}
            />
          </SectionCard>
        )}

        {/* ── Time Performance ── */}
        {(hourly.length > 0 || daily.length > 0) && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {hourly.length > 0 && (
              <SectionCard title="Hourly Performance" description="Performance by hour of day.">
                <DetailTable
                  headers={[
                    { label: "Hour", key: "hour" },
                    { label: "Clicks", key: "clicks", align: "right", render: (v) => fmt(v) },
                    { label: "Spend", key: "spend", align: "right", render: (v) => fmtMYR(v) },
                    { label: "Conv", key: "conversions", align: "right", render: (v) => fmt(v) },
                    { label: "CPA", key: "cpa", align: "right", render: (_v, row) => row.conversions > 0 ? fmtMYR(cpaFor(row)) : <span className="text-text-muted">—</span> },
                  ]}
                  rows={hourly.map((h: any) => ({ ...h, hour: `${String(h.hour ?? h.hour_of_day ?? "").padStart(2, "0")}:00` }))}
                />
              </SectionCard>
            )}
            {dayOfWeekRows.length > 0 && (
              <SectionCard title="Day of Week Performance">
                <DetailTable
                  headers={[
                    { label: "Day", key: "day" },
                    { label: "Clicks", key: "clicks", align: "right", render: (v) => fmt(v) },
                    { label: "Spend", key: "spend", align: "right", render: (v) => fmtMYR(v) },
                    { label: "Conv", key: "conversions", align: "right", render: (v) => fmt(v) },
                    { label: "CPA", key: "cpa", align: "right", render: (v, row) => row.conversions > 0 ? fmtMYR(v) : <span className="text-text-muted">—</span> },
                  ]}
                  rows={dayOfWeekRows}
                />
              </SectionCard>
            )}
          </div>
        )}

      </div>
    </DashboardLayout>
  );
}
