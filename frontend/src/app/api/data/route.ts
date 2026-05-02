import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { resolveClientName } from "@/lib/server-config";

function formatMyr(value: number) {
  return new Intl.NumberFormat("en-MY", { style: "currency", currency: "MYR" }).format(value);
}

function numberOrNull(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function isValidIsoDate(value: unknown) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }

  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}

function enrichRecommendation(raw: any) {
  const actionType = raw.action_type || raw.type || "review";
  const keyword = raw.keyword || null;
  const currentBid = numberOrNull(raw.current_bid);
  const suggestedBid = numberOrNull(raw.suggested_bid);

  let title = raw.title || raw.action || "Recommendation";
  let suggestedAction = raw.suggested_action || raw.action || raw.title || "Review and Apply";

  if (actionType === "bid_adjustment" && currentBid && suggestedBid) {
    const direction = suggestedBid > currentBid ? "Increase" : "Decrease";
    const changePct = ((suggestedBid - currentBid) / currentBid) * 100;
    title = `${direction} bid: ${keyword || title.replace(/^Review:\s*/i, "")}`;
    suggestedAction = (
      `${direction} max CPC bid from ${formatMyr(currentBid)} to ${formatMyr(suggestedBid)} ` +
      `(${changePct >= 0 ? "+" : ""}${changePct.toFixed(1)}%). ` +
      "This updates the keyword-level bid in Google Ads; it does not pause the keyword or change match type."
    );
  }

  const type = actionType.toLowerCase();
  const platform = (raw.platform || "Google").toLowerCase();
  const googleAuto = new Set([
    "bid_adjustment", "budget_change", "keyword_action",
    "ad_copy", "add_negative_keyword"
  ]);
  const metaAuto = new Set([
    "budget_adjustment", "budget_scaling",
    "audience_exclusion", "creative_refresh",
    "placement_exclusion", "geo_exclusion",
    "schedule_adjustment", "day_schedule",
    "geo_scaling"
  ]);
  const hasRequiredTarget = Boolean(raw.target_id || raw.campaign_id || raw.adset_id);
  const legacyAutomationAllowed = (
    ((platform === "google" || platform === "cross-platform") && googleAuto.has(type)) ||
    (platform === "meta" && metaAuto.has(type))
  ) && hasRequiredTarget;
  const backendSentAutomation = typeof raw.automation_allowed === "boolean";
  const automationAllowed = backendSentAutomation ? raw.automation_allowed : legacyAutomationAllowed;
  const guardrailStatus = raw.guardrail_status || "eligible";
  const qualityLabel = raw.quality_label || (automationAllowed && guardrailStatus === "eligible" ? "High confidence" : "Manual only");

  return {
    id: raw.id || raw.recommendation_id || `rec-${Math.random().toString(36).substr(2, 9)}`,
    title,
    description: raw.description || raw.reason || "",
    platform: raw.platform || "Google",
    impact: raw.impact || (raw.priority === "high" ? "High" : raw.priority === "low" ? "Low" : "Medium"),
    actionType,
    status: "Pending",
    expectedImpact: raw.expected_impact || null,
    suggestedAction,
    keyword,
    campaignName: raw.campaign_name || raw.target_id || null,
    ad_group_name: raw.ad_group_name || null,
    target_id: raw.target_id || null,
    campaign_id: raw.campaign_id || null,
    adset_id: raw.adset_id || null,
    normalized_key: raw.normalized_key || null,
    current_bid: currentBid,
    suggested_bid: suggestedBid,
    quality_label: qualityLabel,
    confidence_score: numberOrNull(raw.confidence_score) ?? null,
    guardrail_status: guardrailStatus,
    guardrail_reasons: Array.isArray(raw.guardrail_reasons) ? raw.guardrail_reasons : [],
    evidence: raw.evidence || null,
    automation_allowed: automationAllowed,
    isManualOnly: (() => {
      if (guardrailStatus === "manual_only") return true;
      if (guardrailStatus === "suppressed") return true;
      return !automationAllowed;
    })(),
  };
}

export async function GET(request: Request) {
  const { userId } = await auth();

  if (!userId) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const resolvedClient = resolveClientName(searchParams.get("client"));
  const startDate = searchParams.get("start_date");
  const endDate = searchParams.get("end_date");

  const modalBaseUrl = process.env.MODAL_API_BASE_URL;
  const apiKey = process.env.ADSPULSE_INTERNAL_API_KEY;

  if (!resolvedClient.ok) {
    return NextResponse.json({ error: resolvedClient.error }, { status: resolvedClient.status });
  }

  const hasRange = Boolean(startDate || endDate);
  if (hasRange && (!isValidIsoDate(startDate) || !isValidIsoDate(endDate))) {
    return NextResponse.json({ error: "start_date and end_date must use YYYY-MM-DD format" }, { status: 400 });
  }
  if (hasRange && startDate! > endDate!) {
    return NextResponse.json({ error: "start_date must be before or equal to end_date" }, { status: 400 });
  }

  const clientName = resolvedClient.clientName;

  if (!modalBaseUrl || !apiKey) {
    return NextResponse.json({ error: "Modal dashboard API is not configured" }, { status: 500 });
  }

  const params = new URLSearchParams({ client_name: clientName });
  if (hasRange) {
    params.set("start_date", startDate!);
    params.set("end_date", endDate!);
  }
  const modalUrl = `${modalBaseUrl}?${params.toString()}`;

  try {
    const response = await fetch(modalUrl, {
      headers: {
        "x-api-key": apiKey,
      },
      cache: "no-store"
    });

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(error, { status: response.status });
    }

    const data = await response.json();
    
    // Transform backend data to frontend expected structure
    const mappedData = {
      metrics: {
        totalSpend: data.summary?.total_spend || data.summary?.total_cost || 0,
        totalConversions: data.summary?.total_conversions || 0,
        blendedCPA: data.summary?.cost_per_conversion || 0,
        blendedROAS: 0,
        spendDelta: 0,
        cpaDelta: 0,
        dateRange: data.date_range?.start_date && data.date_range?.end_date
          ? { start: data.date_range.start_date, end: data.date_range.end_date }
          : undefined,
      },
      recommendations: (() => {
        const seen = new Set();
        return (data.recommendations || [])
          .map(enrichRecommendation)
          .filter((rec: any) => {
            if (rec.guardrail_status === "suppressed") return false;
            if (seen.has(rec.id)) return false;
            seen.add(rec.id);
            return true;
          });
      })(),
      campaigns: (data.campaigns || []).map((c: any) => ({
        id: c.campaign_id || c.id || Math.random().toString(),
        name: c.campaign_name || c.name || "Unknown Campaign",
        platform: c.platform || "Google",
        status: c.status === "ENABLED" || c.status === "ACTIVE" ? "Active" : c.status === "PAUSED" ? "Paused" : "Completed",
        spend: c.cost || c.spend || 0,
        conversions: c.conversions || 0,
        cpa: c.cost_per_conversion || c.cpa || 0,
        roas: c.roas || 0,
        impressions: c.impressions || 0,
        clicks: c.clicks || 0,
        // Meta-specific extras
        reach: c.reach,
        frequency: c.frequency,
        ctr: c.ctr,
        cpm: c.cpm,
        objective: c.objective,
      })),
      // --- Google-specific detailed data ---
      search_queries: (data.search_queries || []).map((q: any) => ({
        query: q.query,
        campaign: q.campaign,
        impressions: q.impressions || 0,
        clicks: q.clicks || 0,
        cost: q.cost || 0,
        conversions: q.conversions || 0,
        ctr: q.clicks && q.impressions ? q.clicks / q.impressions : 0,
        cpa: q.conversions > 0 ? q.cost / q.conversions : 0,
      })),
      geo_performance: (data.geo_performance || []).map((g: any) => ({
        location_name: g.location_name,
        campaign_name: g.campaign_name || "",
        impressions: g.impressions || 0,
        clicks: g.clicks || 0,
        cost: g.cost || g.spend || 0,
        conversions: g.conversions || 0,
        ctr: g.ctr || 0,
      })),
      // --- Meta-specific detailed data (passed through from FB metrics) ---
      ad_sets: (data.ad_sets || []).map((a: any) => ({
        adset_name: a.adset_name || a.name || "",
        campaign_name: a.campaign_name || "",
        optimization_goal: a.optimization_goal || "",
        impressions: a.impressions || 0,
        clicks: a.clicks || 0,
        spend: a.spend || 0,
        conversions: a.conversions || 0,
        ctr: a.ctr || 0,
        cpa: a.cost_per_conversion || 0,
        status: a.status || "",
      })),
      demographic_breakdown: (data.demographic_breakdown || []).map((d: any) => ({
        age: d.age,
        gender: d.gender,
        impressions: d.impressions || 0,
        clicks: d.clicks || 0,
        spend: d.spend || 0,
        conversions: d.conversions || 0,
        ctr: d.ctr || 0,
        cpa: d.cost_per_conversion || 0,
      })),
      placement_breakdown: (data.placement_breakdown || []).map((p: any) => ({
        placement_name: p.placement_name || `${p.platform} - ${p.position}`,
        impressions: p.impressions || 0,
        clicks: p.clicks || 0,
        ctr: p.ctr || 0,
        cpm: p.cpm || 0,
        spend: p.spend || 0,
        conversions: p.conversions || 0,
        cpa: p.cost_per_conversion || 0,
      })),
      meta_geo_performance: (data.meta_geo_performance || []).map((g: any) => ({
        location_name: g.location_name,
        clicks: g.clicks || 0,
        spend: g.spend || 0,
        conversions: g.conversions || 0,
        cpa: g.cost_per_conversion || 0,
        ctr: g.ctr || 0,
      })),
      time_performance: data.time_performance || null,
      insights: data.insights || [],
      keywords: (data.keywords || []).map((k: any) => ({
        keyword: k.keyword,
        campaign: k.campaign,
        impressions: k.impressions || 0,
        clicks: k.clicks || 0,
        ctr: k.ctr || 0,
        avg_cpc: k.avg_cpc || 0,
        quality_score: k.quality_score || null,
      })),
      trends: data.trends || null,
      client_name: data.client_name || clientName,
      account_name: data.account_name || clientName,
      customer_id: data.customer_id || null,
      facebook_ad_account_id: data.facebook_ad_account_id || null,
      date_range: data.date_range || null,
      platform_date_ranges: data.platform_date_ranges || null,
    };

    return NextResponse.json(mappedData);
  } catch (error) {
    console.error("Dashboard Data Fetch Error:", error);
    return NextResponse.json({ error: "Failed to fetch dashboard data" }, { status: 500 });
  }
}
