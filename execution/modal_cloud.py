#!/usr/bin/env python3
"""
Modal Cloud Deployment for Ad Optimization Reports
Automatically generates and emails weekly reports for all clients.

Testing Mode: All reports sent to andrea@autoflow-solutions.com
Production Mode: Reports sent to client emails in database

Schedule: Every Monday 8 AM Malaysia Time (GMT+8)
"""

import modal
from datetime import datetime, timedelta
import json
import os
import re
import sys
import base64
from pathlib import Path
from typing import Optional

# ============================================================================
# MODAL APP CONFIGURATION
# ============================================================================

app = modal.App("ad-optimization-reports")

# Persistent volume for client database
volume = modal.Volume.from_name("client-data", create_if_missing=True)

# Project root for loading local files
project_root = Path(__file__).parent.parent

# Modal image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "google-ads>=28.0.0",
        "facebook-business>=19.0.0",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
        "gspread>=6.0.0",
        "oauth2client>=4.1.3",
        "google-auth>=2.27.0",
        "google-auth-oauthlib>=1.2.0",
        "google-auth-httplib2>=0.2.0",
        "pandas>=2.2.0",
        "numpy>=1.26.0",
        "fastapi",
        "uvicorn",
        "pydantic",
    )
    .add_local_file(project_root / "execution" / "fetch_google_ads_metrics.py", "/root/fetch_google_ads_metrics.py")
    .add_local_file(project_root / "execution" / "fetch_facebook_ads_metrics.py", "/root/fetch_facebook_ads_metrics.py")
    .add_local_file(project_root / "execution" / "create_full_insights.py", "/root/create_full_insights.py")
    .add_local_file(project_root / "execution" / "create_facebook_insights.py", "/root/create_facebook_insights.py")
    .add_local_file(project_root / "execution" / "create_html_dashboard.py", "/root/create_html_dashboard.py")
    .add_local_file(project_root / "execution" / "create_facebook_html_dashboard.py", "/root/create_facebook_html_dashboard.py")
    .add_local_file(project_root / "execution" / "analyze_week2_insights.py", "/root/analyze_week2_insights.py")
    .add_local_file(project_root / "execution" / "analyze_advanced_insights.py", "/root/analyze_advanced_insights.py")
    .add_local_file(project_root / "execution" / "analyze_facebook_insights.py", "/root/analyze_facebook_insights.py")
    .add_local_file(project_root / "execution" / "google_ads_executor.py", "/root/google_ads_executor.py")
    .add_local_file(project_root / "execution" / "meta_ads_executor.py", "/root/meta_ads_executor.py")
    .add_local_file(project_root / "execution" / "utils.py", "/root/utils.py")
    .add_local_file(project_root / "execution" / "impact_models.py", "/root/impact_models.py")
    .add_local_file(project_root / "execution" / "calculate_total_impact.py", "/root/calculate_total_impact.py")
    .add_local_file(project_root / "execution" / "generate_dashboard_data.py", "/root/generate_dashboard_data.py")
    .add_local_file(project_root / "execution" / "apply_recommendations.py", "/root/apply_recommendations.py")
)

# Testing mode - send all emails to this address
TESTING_MODE = False
TEST_EMAIL = "andrea@autoflow-solutions.com"

def normalize_days(days, default=30):
    try:
        parsed = int(days)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, 90))

def resolve_report_date_range(days=None, start_date=None, end_date=None):
    if start_date or end_date:
        if not start_date or not end_date:
            raise ValueError("Both start_date and end_date are required for a custom range")
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Dates must use YYYY-MM-DD format") from exc
        if start > end:
            raise ValueError("start_date must be before or equal to end_date")
        return start, end, max(1, (end - start).days)

    resolved_days = normalize_days(days)
    end = datetime.now()
    start = end - timedelta(days=resolved_days)
    return start, end, resolved_days

def date_range_days(start_date, end_date):
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        return max(1, (end - start).days)
    except Exception:
        return None

def range_matches(data_range, start_date, end_date):
    return (
        data_range
        and data_range.get("start_date") == start_date
        and data_range.get("end_date") == end_date
    )

def range_is_covered(data_range, start_date, end_date):
    return (
        data_range
        and data_range.get("start_date") <= start_date
        and data_range.get("end_date") >= end_date
    )

def aggregate_google_daily(rows, start_date, end_date):
    grouped = {}
    for row in rows or []:
        row_date = row.get("date")
        if not row_date:
            continue
        if row_date < start_date or row_date > end_date:
            continue
        key = str(row.get("id") or row.get("name"))
        item = grouped.setdefault(key, {
            "id": row.get("id"),
            "name": row.get("name", "Unknown Campaign"),
            "status": row.get("status", "UNKNOWN"),
            "type": row.get("type", ""),
            "spend": 0,
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "conversion_value": 0,
            "platform": "Google",
        })
        item["spend"] += row.get("cost", 0) or 0
        item["impressions"] += row.get("impressions", 0) or 0
        item["clicks"] += row.get("clicks", 0) or 0
        item["conversions"] += row.get("conversions", 0) or 0
        item["conversion_value"] += row.get("conversion_value", 0) or 0

    campaigns = []
    for item in grouped.values():
        item["spend"] = round(item["spend"], 2)
        item["conversions"] = round(item["conversions"], 2)
        item["ctr"] = item["clicks"] / item["impressions"] if item["impressions"] else 0
        item["cpa"] = round(item["spend"] / item["conversions"], 2) if item["conversions"] else 0
        item["cost_per_conversion"] = item["cpa"]
        item["roas"] = item["conversion_value"] / item["spend"] if item["spend"] else 0
        campaigns.append(item)

    return sorted(campaigns, key=lambda x: x.get("spend", 0), reverse=True)

def percent_change(current, previous, inverse=False):
    if previous is None or previous == 0:
        return None
    change = ((current - previous) / previous) * 100
    if inverse:
        change *= -1
    return round(change, 1)

def previous_date_range(start_date, end_date):
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except Exception:
        return None, None
    days = max(1, (end - start).days + 1)
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    return previous_start.strftime("%Y-%m-%d"), previous_end.strftime("%Y-%m-%d")

def google_trends_from_daily(rows, start_date, end_date):
    previous_start, previous_end = previous_date_range(start_date, end_date)
    if not previous_start or not previous_end:
        return None

    available_dates = [row.get("date") for row in rows or [] if row.get("date")]
    if not available_dates or min(available_dates) > previous_start:
        return None

    current = summarize_campaigns(aggregate_google_daily(rows, start_date, end_date))
    previous = summarize_campaigns(aggregate_google_daily(rows, previous_start, previous_end))
    if previous.get("total_spend", 0) == 0 and previous.get("total_conversions", 0) == 0:
        return None

    return {
        "spend_change": percent_change(current.get("total_spend", 0), previous.get("total_spend", 0)),
        "conversions_change": percent_change(current.get("total_conversions", 0), previous.get("total_conversions", 0)),
        "cpa_change": percent_change(
            current.get("cost_per_conversion", 0),
            previous.get("cost_per_conversion", 0),
            inverse=True,
        ),
        "quality_score_change": None,
        "comparison_range": {
            "start_date": previous_start,
            "end_date": previous_end,
        },
    }

def aggregate_meta_daily(rows, start_date, end_date, campaign_lookup=None):
    campaign_lookup = campaign_lookup or {}
    grouped = {}
    for row in rows or []:
        row_date = row.get("date")
        if not row_date:
            continue
        if row_date < start_date or row_date > end_date:
            continue
        key = str(row.get("campaign_id") or row.get("campaign_name"))
        lookup = campaign_lookup.get(row.get("campaign_id"), {})
        item = grouped.setdefault(key, {
            "campaign_id": row.get("campaign_id"),
            "campaign_name": row.get("campaign_name", "Unknown Campaign"),
            "objective": row.get("objective") or lookup.get("objective", ""),
            "status": lookup.get("status", "UNKNOWN"),
            "spend": 0,
            "impressions": 0,
            "reach": 0,
            "clicks": 0,
            "unique_clicks": 0,
            "conversions": 0,
            "conversion_value": 0,
            "platform": "Meta",
        })
        item["spend"] += row.get("spend", 0) or 0
        item["impressions"] += row.get("impressions", 0) or 0
        item["reach"] += row.get("reach", 0) or 0
        item["clicks"] += row.get("clicks", 0) or 0
        item["unique_clicks"] += row.get("unique_clicks", 0) or 0
        item["conversions"] += row.get("conversions", 0) or 0
        item["conversion_value"] += row.get("conversion_value", 0) or 0

    campaigns = []
    for item in grouped.values():
        item["spend"] = round(item["spend"], 2)
        item["conversions"] = round(item["conversions"], 2)
        item["ctr"] = (item["clicks"] / item["impressions"] * 100) if item["impressions"] else 0
        item["frequency"] = item["impressions"] / item["reach"] if item["reach"] else 0
        item["cost_per_conversion"] = round(item["spend"] / item["conversions"], 2) if item["conversions"] else 0
        item["roas"] = item["conversion_value"] / item["spend"] if item["spend"] else 0
        campaigns.append(item)

    return sorted(campaigns, key=lambda x: x.get("spend", 0), reverse=True)

def summarize_campaigns(campaigns):
    total_spend = sum(c.get("spend", c.get("cost", 0)) or 0 for c in campaigns)
    total_conversions = sum(c.get("conversions", 0) or 0 for c in campaigns)
    total_impressions = sum(c.get("impressions", 0) or 0 for c in campaigns)
    total_clicks = sum(c.get("clicks", 0) or 0 for c in campaigns)
    return {
        "total_spend": round(total_spend, 2),
        "total_cost": round(total_spend, 2),
        "total_conversions": round(total_conversions, 2),
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "cost_per_conversion": round(total_spend / total_conversions, 2) if total_conversions else 0,
    }

def load_clients():
    clients_file = Path("/data/clients.json")
    if not clients_file.exists():
        raise FileNotFoundError("No /data/clients.json found in Modal volume. Add clients before deploying.")
    with open(clients_file) as f:
        return json.load(f)

def save_clients(clients):
    clients_file = Path("/data/clients.json")
    with open(clients_file, "w") as f:
        json.dump(clients, f, indent=2)
    volume.commit()

def parse_email_recipients(value):
    if not value:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = str(value).replace("\n", ",").split(",")
    return [item.strip() for item in raw_items if item and item.strip()]

def default_email_settings(client_name, client_data):
    return {
        "enabled": False,
        "recipients": parse_email_recipients(client_data.get("email")),
        "frequency": "weekly",
        "send_day": "Monday",
        "send_time": "08:00",
        "timezone": "Asia/Kuala_Lumpur",
        "subject": "Weekly Ad Performance Report - {client_name}",
        "message": (
            "Hello {client_name},\n\n"
            "Your advertising performance report is ready.\n\n"
            "Total Spend: RM {total_spend}\n"
            "Total Conversions: {total_conversions}\n"
            "Average CPA: RM {avg_cpa}\n\n"
            "Detailed reports are attached."
        ),
        "attachments": {
            "google_html": True,
            "meta_html": True,
            "summary_csv": False,
        },
    }

def normalize_email_settings(client_name, client_data):
    settings = default_email_settings(client_name, client_data)
    saved = client_data.get("email_reports") or {}
    settings.update({k: v for k, v in saved.items() if k != "attachments"})
    settings["recipients"] = parse_email_recipients(settings.get("recipients"))
    attachments = settings["attachments"].copy()
    attachments.update(saved.get("attachments") or {})
    settings["attachments"] = attachments
    return settings

def format_metric(value):
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"

def normalize_match_value(value):
    if value is None:
        return ""
    return " ".join(str(value).replace('"', "").replace("'", "").strip().lower().split())

def recommendation_match_key(item):
    action_type = normalize_match_value(item.get("action_type") or item.get("actionType") or item.get("type"))
    platform = normalize_match_value(item.get("platform"))
    keyword = normalize_match_value(item.get("keyword"))
    target = normalize_match_value(
        item.get("target_id")
        or item.get("adset_id")
        or item.get("ad_group_name")
        or item.get("adGroupName")
    )
    campaign = normalize_match_value(
        item.get("campaign_id")
        or item.get("campaign_name")
        or item.get("campaignName")
    )

    if action_type and keyword:
        return f"{platform}|{action_type}|keyword:{keyword}|target:{target}|campaign:{campaign}"
    if action_type and target:
        return f"{platform}|{action_type}|target:{target}|campaign:{campaign}"
    if action_type and campaign:
        return f"{platform}|{action_type}|campaign:{campaign}"
    return ""

def recommendation_fallback_key(item):
    action_type = normalize_match_value(item.get("action_type") or item.get("actionType") or item.get("type"))
    platform = normalize_match_value(item.get("platform"))
    keyword = normalize_match_value(item.get("keyword"))
    if action_type and keyword:
        return f"{platform}|{action_type}|keyword:{keyword}"
    return ""

REVENUE_RECOMMENDATION_TYPES = {"roas_scaling", "roas_review"}
WASTE_ACTION_TYPES = {
    "add_negative_keyword",
    "keyword_action",
    "audience_exclusion",
    "placement_exclusion",
    "geo_exclusion",
    "campaign_review",
}
SCALE_ACTION_TYPES = {"budget_scaling", "geo_scaling"}
CREATIVE_REVIEW_ACTION_TYPES = {
    "creative_refresh",
    "schedule_adjustment",
    "day_schedule",
    "audience_fatigue",
    "objective_mismatch",
    "creative_test",
    "landing_page",
    "quality_improvement",
    "ad_copy",
    "budget_adjustment",
}
AUTOMATABLE_ACTION_TYPES = {
    "add_negative_keyword",
    "keyword_action",
    "bid_adjustment",
    "budget_adjustment",
    "budget_scaling",
}
HIGH_RISK_REVIEW_ACTION_TYPES = {
    "keyword_action",
    "budget_scaling",
    "budget_adjustment",
    "geo_scaling",
    "audience_exclusion",
    "placement_exclusion",
    "geo_exclusion",
    "campaign_review",
}

def normalized_recommendation_key(item):
    return recommendation_match_key(item) or recommendation_fallback_key(item)

def first_number(pattern, text):
    if not text:
        return None
    match = re.search(pattern, str(text), flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except (TypeError, ValueError, IndexError):
        return None

def first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None

def find_matching_row(rows, keyword=None, campaign=None, target=None):
    keyword_norm = normalize_match_value(keyword)
    campaign_norm = normalize_match_value(campaign)
    target_norm = normalize_match_value(target)
    for row in rows or []:
        row_keyword = normalize_match_value(row.get("query") or row.get("search_term") or row.get("keyword") or row.get("keyword_text"))
        row_campaign = normalize_match_value(row.get("campaign") or row.get("campaign_name") or row.get("name"))
        row_target = normalize_match_value(row.get("target_id") or row.get("ad_group_name") or row.get("adset_name"))
        if keyword_norm and row_keyword and keyword_norm == row_keyword:
            return row
        if campaign_norm and row_campaign and campaign_norm == row_campaign:
            return row
        if target_norm and row_target and target_norm == row_target:
            return row
    return None

def infer_recommendation_evidence(rec, data, date_days):
    description = rec.get("description") or rec.get("reason") or ""
    impact_data = rec.get("impact_data") or {}
    campaign = rec.get("campaign_name") or rec.get("campaignName")
    target = rec.get("target_id") or rec.get("ad_group_name") or rec.get("adset_name")
    keyword = rec.get("keyword")

    rows = []
    rows.extend(data.get("search_queries") or [])
    rows.extend(data.get("keywords") or [])
    rows.extend(data.get("campaigns") or [])
    rows.extend(data.get("ad_sets") or [])
    rows.extend(data.get("placement_breakdown") or [])
    rows.extend(data.get("demographic_breakdown") or [])
    rows.extend(data.get("meta_geo_performance") or [])
    matched = find_matching_row(rows, keyword=keyword, campaign=campaign, target=target) or {}

    spend = first_present(
        safe_number(rec.get("spend"), None)
        , safe_number(rec.get("cost"), None)
        , safe_number(matched.get("spend"), None)
        , safe_number(matched.get("cost"), None)
        , first_number(r"(?:wasted|spent|spend)\s+(?:rm|myr)?\s*([0-9][0-9,.]*)", description)
        , first_number(r"(?:rm|myr)\s*([0-9][0-9,.]*)", description)
    )
    conversions = first_present(
        safe_number(rec.get("conversions"), None)
        , safe_number(matched.get("conversions"), None)
    )
    parsed_conversions = first_number(r"([0-9][0-9,.]*)\s+conversions?", description)
    if conversions is None and parsed_conversions is not None:
        conversions = parsed_conversions
    if conversions is None and re.search(r"\bzero conversions?\b|\b0 conversions?\b", description, re.IGNORECASE):
        conversions = 0

    clicks = first_present(safe_number(rec.get("clicks"), None), safe_number(matched.get("clicks"), None))
    parsed_clicks = first_number(r"([0-9][0-9,.]*)\s+clicks?", description)
    if clicks is None and parsed_clicks is not None:
        clicks = parsed_clicks

    cpa = first_present(
        safe_number(rec.get("cpa") or rec.get("cost_per_conversion"), None)
        , safe_number(matched.get("cpa") or matched.get("cost_per_conversion"), None)
        , first_number(r"(?:rm|myr)\s*([0-9][0-9,.]*)\s+cpa", description)
        , first_number(r"cpa\s+(?:rm|myr)?\s*([0-9][0-9,.]*)", description)
    )
    if spend is None and cpa is not None and conversions:
        spend = cpa * conversions

    confidence_score = safe_number(impact_data.get("confidence_pct"), None)
    if confidence_score is None:
        confidence_score = first_number(r"([0-9]{2,3})%\s+confidence", rec.get("expected_impact") or "")
    if confidence_score is None:
        confidence_score = 80 if normalize_match_value(rec.get("impact")) == "high" else 65

    return {
        "spend": round(spend, 2) if spend is not None else None,
        "clicks": round(clicks, 2) if clicks is not None else None,
        "conversions": round(conversions, 2) if conversions is not None else None,
        "cpa": round(cpa, 2) if cpa is not None else None,
        "date_range_days": date_days,
        "confidence_inputs": {
            "impact_confidence": impact_data.get("confidence"),
            "impact_confidence_pct": confidence_score,
        },
    }

def conversion_value_tracking_available(data):
    summary = data.get("summary") or {}
    if safe_number(summary.get("total_conversion_value"), 0) > 0:
        return True
    for campaign in data.get("campaigns") or []:
        if safe_number(campaign.get("conversion_value"), 0) > 0:
            return True
    return False

def platform_average_cpa(data, platform):
    platform_norm = normalize_match_value(platform)
    campaigns = []
    for campaign in data.get("campaigns") or []:
        campaign_platform = normalize_match_value(campaign.get("platform") or "Google")
        if platform_norm == "meta":
            matches = campaign_platform == "meta"
        elif platform_norm == "google":
            matches = campaign_platform in {"", "google"}
        else:
            matches = True
        if matches:
            campaigns.append(campaign)
    summary = summarize_campaigns(campaigns)
    return safe_number(summary.get("cost_per_conversion"), 0)

def needs_high_risk_review(action_type, rec, conversions=None):
    action_type_norm = normalize_match_value(action_type)
    if action_type_norm == "bid_adjustment":
        current_bid = safe_number(rec.get("current_bid"), None)
        suggested_bid = safe_number(rec.get("suggested_bid"), None)
        return current_bid is not None and suggested_bid is not None and suggested_bid > current_bid
    if action_type_norm == "add_negative_keyword":
        return conversions not in (None, 0)
    return action_type_norm in HIGH_RISK_REVIEW_ACTION_TYPES

def downgrade_label(action_type, rec, conversions=None):
    return "Needs review" if needs_high_risk_review(action_type, rec, conversions) else "Manual only"

def strip_unsupported_revenue_copy(text):
    if not text:
        return text
    cleaned = re.sub(r",?\s*\+?(?:RM|MYR)\s*[0-9][0-9,.]*\s+revenue(?:/month| monthly)?", "", str(text), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+and\s+revenue", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,")

def platform_state_matches(rec, data):
    action_type = rec.get("action_type") or rec.get("type")
    keyword = normalize_match_value(rec.get("keyword"))
    campaign = normalize_match_value(rec.get("campaign_name") or rec.get("campaignName"))
    target = normalize_match_value(rec.get("target_id") or rec.get("ad_group_name"))

    if action_type == "add_negative_keyword" and keyword:
        for neg in data.get("negative_keywords") or data.get("google_negative_keywords") or []:
            neg_keyword = normalize_match_value(neg.get("keyword") or neg.get("text") or neg.get("negative_keyword"))
            neg_campaign = normalize_match_value(neg.get("campaign_name") or neg.get("campaign"))
            if neg_keyword == keyword and (not campaign or not neg_campaign or neg_campaign == campaign):
                return True, "Negative keyword already exists in cached Google Ads data."

    if action_type == "keyword_action" and normalize_match_value(rec.get("suggested")) == "paused":
        for row in data.get("keywords") or []:
            row_target = normalize_match_value(row.get("resource_name") or row.get("target_id"))
            row_keyword = normalize_match_value(row.get("keyword") or row.get("keyword_text"))
            row_status = normalize_match_value(row.get("status"))
            if row_status == "paused" and ((target and row_target == target) or (keyword and row_keyword == keyword)):
                return True, "Keyword is already paused in cached Google Ads data."

    return False, None

def apply_recommendation_guardrails(data):
    date_range = data.get("date_range") or {}
    date_days = date_range.get("days") or date_range_days(date_range.get("start_date"), date_range.get("end_date"))
    has_conversion_value = conversion_value_tracking_available(data)
    guarded = []

    for rec in data.get("recommendations") or []:
        rec = dict(rec)
        action_type = rec.get("action_type") or rec.get("type") or "review"
        action_type_norm = normalize_match_value(action_type)
        platform_cpa = platform_average_cpa(data, rec.get("platform") or "Google")
        reasons = []
        unsupported_metric = False

        unsupported_text = str(rec.get("title", "")) + " " + str(rec.get("description", ""))
        if action_type_norm in REVENUE_RECOMMENDATION_TYPES or re.search(r"\broas\b|\brevenue\b", unsupported_text, re.IGNORECASE):
            unsupported_metric = True
            reasons.append("ROAS/revenue recommendation disabled until conversion value tracking is verified.")

        evidence = infer_recommendation_evidence(rec, data, date_days)
        confidence_score = int(max(0, min(100, safe_number(evidence["confidence_inputs"].get("impact_confidence_pct"), 0))))
        automation = rec.get("automation") or {}
        has_required_ids = bool(rec.get("target_id") or rec.get("campaign_id") or rec.get("adset_id"))
        automation_allowed = bool(
            automation.get("is_automatable", action_type_norm in AUTOMATABLE_ACTION_TYPES)
            and action_type_norm in AUTOMATABLE_ACTION_TYPES
            and has_required_ids
        )
        guardrail_status = "eligible"
        quality_label = "High confidence" if confidence_score >= 70 else "Manual only"

        if unsupported_metric and not has_conversion_value:
            guardrail_status = "suppressed"
            quality_label = "Insufficient data"

        state_applied, state_reason = platform_state_matches(rec, data)
        if state_applied:
            guardrail_status = "suppressed"
            quality_label = "High confidence"
            reasons.append(state_reason)

        spend = evidence.get("spend")
        clicks = evidence.get("clicks")
        conversions = evidence.get("conversions")
        cpa = evidence.get("cpa")
        current_bid = safe_number(rec.get("current_bid"), None)
        suggested_bid = safe_number(rec.get("suggested_bid"), None)
        is_bid_decrease = action_type_norm == "bid_adjustment" and current_bid is not None and suggested_bid is not None and suggested_bid < current_bid
        is_bid_increase = action_type_norm == "bid_adjustment" and current_bid is not None and suggested_bid is not None and suggested_bid > current_bid

        if date_days and date_days < 7 and guardrail_status != "suppressed":
            reasons.append("Short date range; prioritize high-signal recommendations.")
            if confidence_score < 70 and (spend is None or spend < 20):
                guardrail_status = "manual_only"
                quality_label = downgrade_label(action_type_norm, rec, conversions)
                automation_allowed = False

        if action_type_norm in WASTE_ACTION_TYPES and guardrail_status != "suppressed":
            if spend is None or spend < 5:
                guardrail_status = "suppressed"
                quality_label = "Insufficient data"
                reasons.append("Spend is below the minimum evidence threshold.")
            elif spend < 10 and (clicks is None or clicks < 5):
                guardrail_status = "manual_only"
                quality_label = "Manual only"
                automation_allowed = False
                reasons.append("Waste signal is useful but below the auto-apply threshold.")
            if conversions not in (None, 0):
                guardrail_status = "manual_only"
                quality_label = downgrade_label(action_type_norm, rec, conversions)
                automation_allowed = False
                reasons.append("This item has conversions, so it requires manual review.")

        if is_bid_decrease and guardrail_status != "suppressed":
            if spend is None or spend < 10 or conversions not in (None, 0):
                guardrail_status = "manual_only"
                quality_label = downgrade_label(action_type_norm, rec, conversions)
                automation_allowed = False
                reasons.append("Bid decrease needs clearer waste evidence before automatic apply.")
            elif has_required_ids:
                guardrail_status = "eligible"
                automation_allowed = True

        if (action_type_norm in SCALE_ACTION_TYPES or is_bid_increase) and guardrail_status != "suppressed":
            if conversions is None or conversions < 2 or spend is None or spend < 10:
                guardrail_status = "manual_only"
                quality_label = downgrade_label(action_type_norm, rec, conversions)
                automation_allowed = False
                reasons.append("Not enough conversion volume for automatic scaling.")
            elif cpa and platform_cpa and cpa > platform_cpa * 1.2:
                guardrail_status = "manual_only"
                quality_label = downgrade_label(action_type_norm, rec, conversions)
                automation_allowed = False
                reasons.append("CPA is too far above the account average for automatic scaling.")

        if action_type_norm == "budget_scaling" and guardrail_status != "suppressed":
            if conversions is None or conversions < 5:
                guardrail_status = "manual_only"
                quality_label = "Needs review"
                automation_allowed = False
                reasons.append("Budget scaling requires at least 5 conversions.")

        if action_type_norm in CREATIVE_REVIEW_ACTION_TYPES and guardrail_status == "eligible":
            guardrail_status = "manual_only"
            quality_label = "Manual only"
            automation_allowed = False
            reasons.append("This recommendation requires human review or creative/platform setup.")

        if not automation_allowed and guardrail_status == "eligible":
            guardrail_status = "manual_only"
            quality_label = "Manual only"
            reasons.append("No safe automated action is available for this recommendation.")

        if guardrail_status == "eligible" and automation_allowed:
            quality_label = "High confidence" if confidence_score >= 70 else "Manual only"

        rec["normalized_key"] = normalized_recommendation_key(rec)
        rec["quality_label"] = quality_label
        rec["confidence_score"] = confidence_score
        rec["guardrail_status"] = guardrail_status
        rec["guardrail_reasons"] = list(dict.fromkeys([r for r in reasons if r]))
        rec["evidence"] = evidence
        rec["automation_allowed"] = automation_allowed and guardrail_status == "eligible"
        rec["expected_impact"] = strip_unsupported_revenue_copy(rec.get("expected_impact"))
        if guardrail_status != "suppressed":
            guarded.append(rec)

    data["recommendations"] = guarded
    return data

# ============================================================================
# HELPER: SETUP CREDENTIALS
# ============================================================================

def setup_credentials():
    """Reconstruct credentials.json from Base64 environment variable"""
    google_creds_base64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')
    if google_creds_base64:
        try:
            with open('/root/credentials.json', 'wb') as f:
                f.write(base64.b64decode(google_creds_base64))
        except Exception as e:
            print(f"Failed to reconstruct credentials.json: {e}")

    google_token_base64 = os.getenv('GOOGLE_TOKEN_BASE64')
    if google_token_base64:
        try:
            with open('/root/token.json', 'wb') as f:
                f.write(base64.b64decode(google_token_base64))
        except Exception as e:
            print(f"Failed to reconstruct token.json: {e}")

# ============================================================================
# REPORT GENERATION - PER CLIENT
# ============================================================================

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("google-ads-creds"),
        modal.Secret.from_name("facebook-ads-creds"),
        modal.Secret.from_name("smtp-creds"),
        modal.Secret.from_name("google-credentials"),
    ],
    volumes={"/data": volume},
    timeout=1200,
)
def generate_client_report(
    client_name: str,
    customer_id: str = None,
    facebook_ad_account_id: str = None,
    email: str = None,
    send_email: bool = False,
    days: int = 30,
    start_date: str = None,
    end_date: str = None,
    email_settings: dict = None
):
    import os
    import shutil
    import glob
    import sys
    
    os.makedirs("/tmp", exist_ok=True)
    setup_credentials()
    
    start_date, end_date, days = resolve_report_date_range(days, start_date, end_date)
    
    dashboards = []
    summary = {}
    errors = []
    
    sys.path.insert(0, '/root')

    # 1. GOOGLE ADS
    if customer_id:
        try:
            print(f"📊 Processing Google Ads for {client_name}...")
            import fetch_google_ads_metrics
            import create_full_insights
            import create_html_dashboard

            sys.argv = [
                'fetch_google_ads_metrics',
                '--customer_id', customer_id,
                '--start_date', start_date.strftime('%Y-%m-%d'),
                '--end_date', end_date.strftime('%Y-%m-%d'),
                '--output_dir', '/tmp'
            ]
            metrics_file = fetch_google_ads_metrics.main()
            
            customer_id_str = customer_id.replace('-', '')
            insights_file = f"/tmp/insights_enhanced_{customer_id_str}.json"
            recs_file = f"/tmp/recommendations_enhanced_{customer_id_str}.json"
            
            create_full_insights.create_enhanced_insights(metrics_file, insights_file, recs_file)
            
            google_dashboard_path = f"/tmp/google_ads_dashboard_{customer_id_str}.html"
            sys.argv = [
                'create_html_dashboard',
                '--metrics_file', metrics_file,
                '--insights_file', insights_file,
                '--recommendations_file', recs_file,
                '--output_file', google_dashboard_path
            ]
            create_html_dashboard.main()

            # Mirror to volume for Dashboard
            shutil.copy2(metrics_file, f"/data/google_ads_metrics_{customer_id_str}.json")
            shutil.copy2(insights_file, f"/data/google_ads_insights_{customer_id_str}.json")
            shutil.copy2(recs_file, f"/data/google_ads_recommendations_{customer_id_str}.json")
            shutil.copy2(google_dashboard_path, f"/data/google_ads_dashboard_{customer_id_str}.html")
            volume.commit()

            with open(google_dashboard_path, 'r') as f:
                dashboards.append((f"Google_Ads_Report_{client_name}.html", f.read()))
                
            # Email metrics
            with open(metrics_file, 'r') as f:
                m_data = json.load(f)
                m_summary = m_data.get('summary', {})
                summary['google_spend'] = m_summary.get('total_cost', 0)
                summary['google_conversions'] = m_summary.get('total_conversions', 0)

        except Exception as e:
            print(f"ERROR Google Ads: {str(e)}")
            errors.append(f"Google Ads: {str(e)}")

    # 2. FACEBOOK ADS
    if facebook_ad_account_id:
        try:
            print(f"📊 Processing Facebook Ads for {client_name}...")
            import fetch_facebook_ads_metrics
            import create_facebook_insights
            import create_facebook_html_dashboard

            sys.argv = [
                'fetch_facebook_ads_metrics',
                '--ad_account_id', facebook_ad_account_id,
                '--start_date', start_date.strftime('%Y-%m-%d'),
                '--end_date', end_date.strftime('%Y-%m-%d'),
                '--output_dir', '/tmp'
            ]
            metrics_file = fetch_facebook_ads_metrics.main()
            
            sys.argv = [
                'create_facebook_insights',
                '--metrics_file', metrics_file,
                '--output_dir', '/tmp'
            ]
            insights_file, fb_recs_file = create_facebook_insights.main()
            
            sys.argv = [
                'create_facebook_html_dashboard',
                '--metrics_file', metrics_file,
                '--insights_file', insights_file,
                '--recommendations_file', fb_recs_file,
                '--output_dir', '/tmp'
            ]
            create_facebook_html_dashboard.main()
            
            # Find the generated dashboard file
            fb_dashboard_files = glob.glob(f"/tmp/facebook_ads_dashboard_*.html")
            fb_dashboard_path = sorted(fb_dashboard_files)[-1]

            # Mirror to volume for Dashboard
            fb_id = facebook_ad_account_id.replace('act_', '')
            shutil.copy2(metrics_file, f"/data/facebook_ads_metrics_{fb_id}.json")
            shutil.copy2(insights_file, f"/data/facebook_ads_insights_{fb_id}.json")
            shutil.copy2(fb_recs_file, f"/data/facebook_ads_recommendations_{fb_id}.json")
            shutil.copy2(fb_dashboard_path, f"/data/facebook_ads_dashboard_{fb_id}.html")
            volume.commit()

            with open(fb_dashboard_path, 'r') as f:
                dashboards.append((f"Facebook_Ads_Report_{client_name}.html", f.read()))
                
            # Email metrics
            with open(metrics_file, 'r') as f:
                fb_data = json.load(f)
                fb_summary = fb_data.get('summary', {})
                summary['facebook_spend'] = fb_summary.get('total_spend', 0)
                summary['facebook_conversions'] = fb_summary.get('total_conversions', 0)

        except Exception as e:
            print(f"ERROR Facebook Ads: {str(e)}")
            errors.append(f"Facebook Ads: {str(e)}")
        except SystemExit:
            print(f"ERROR Facebook Ads: Script exited early")
            errors.append(f"Facebook Ads: Script exited early")

    # 3. SEND EMAIL
    if dashboards and send_email and email:
        send_email_report.remote(
            client_name=client_name,
            email=email,
            dashboards=dashboards,
            summary=summary,
            errors=errors,
            date_range=(start_date, end_date),
            email_settings=email_settings,
        )
    elif dashboards:
        print(f"Data refreshed for {client_name}; email delivery disabled")
    else:
        print(f"❌ No dashboards generated for {client_name}")

# ============================================================================
# EMAIL SENDING
# ============================================================================

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("smtp-creds")]
)
def send_email_report(client_name, email, dashboards, summary, errors, date_range, email_settings=None):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.application import MIMEApplication
    from email.utils import formataddr

    start_date, end_date = date_range
    total_spend = summary.get('google_spend', 0) + summary.get('facebook_spend', 0)
    total_conv = int(round(summary.get('google_conversions', 0) + summary.get('facebook_conversions', 0)))
    avg_cpa = total_spend / total_conv if total_conv > 0 else 0
    settings = email_settings or {}
    attachments = settings.get("attachments") or {}

    msg = MIMEMultipart()
    msg['From'] = formataddr(("YCK Ads Dashboard", os.getenv('SMTP_USER')))
    msg['To'] = email
    subject_template = settings.get("subject") or "Weekly Ad Performance Report - {client_name}"
    msg['Subject'] = subject_template.format(
        client_name=client_name,
        total_spend=format_metric(total_spend),
        total_conversions=total_conv,
        avg_cpa=format_metric(avg_cpa),
    )

    body_template = settings.get("message") or (
        "Hello {client_name},\n\n"
        "Your advertising performance report is ready.\n\n"
        "Total Spend: RM {total_spend}\n"
        "Total Conversions: {total_conversions}\n"
        "Average CPA: RM {avg_cpa}\n\n"
        "Detailed reports are attached."
    )
    body = body_template.format(
        client_name=client_name,
        total_spend=format_metric(total_spend),
        total_conversions=total_conv,
        avg_cpa=format_metric(avg_cpa),
    )
    msg.attach(MIMEText(body, 'plain'))

    for filename, html_content in dashboards:
        is_google = filename.lower().startswith("google")
        is_meta = filename.lower().startswith(("facebook", "meta"))
        if is_google and not attachments.get("google_html", True):
            continue
        if is_meta and not attachments.get("meta_html", True):
            continue
        attachment = MIMEApplication(html_content.encode('utf-8'), _subtype='html')
        attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(attachment)

    if attachments.get("summary_csv"):
        csv_content = (
            "metric,value\n"
            f"total_spend,{total_spend:.2f}\n"
            f"total_conversions,{total_conv}\n"
            f"average_cpa,{avg_cpa:.2f}\n"
        )
        attachment = MIMEApplication(csv_content.encode('utf-8'), _subtype='csv')
        attachment.add_header('Content-Disposition', 'attachment', filename=f"Summary_{client_name}.csv")
        msg.attach(attachment)

    recipients = [addr.strip() for addr in email.split(',') if addr.strip()]
    with smtplib.SMTP(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT'))) as server:
        server.starttls()
        server.login(os.getenv('SMTP_USER'), os.getenv('SMTP_PASSWORD'))
        server.sendmail(os.getenv('SMTP_USER'), recipients, msg.as_string())
    print(f"✅ Email sent to {recipients}")

# ============================================================================
# CLI COMMANDS (for manual testing)
# ============================================================================

@app.local_entrypoint()
def test_single_client(client_name: str = "YAP CHAN KOR"):
    """Test report generation for a single client (run locally)."""
    print(f"Testing report generation for: {client_name}")

    # Load client data
    import json
    with open('.tmp/clients.json') as f:
        clients = json.load(f)

    client_data = clients.get(client_name)
    if not client_data:
        print(f"❌ Client not found: {client_name}")
        return

    # Generate report
    generate_client_report.remote(
        client_name=client_name,
        customer_id=client_data.get('customer_id'),
        facebook_ad_account_id=client_data.get('facebook_ad_account_id'),
        email=TEST_EMAIL,
        send_email=True,
        days=7
    )

    print(f"✅ Test complete - check {TEST_EMAIL} for report")

# ============================================================================
# WEB API ENDPOINTS
# ============================================================================

from fastapi import FastAPI, Header, HTTPException, Request, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

web_app = FastAPI()

class ApplyRequest(BaseModel):
    client_name: str
    recommendation_id: str
    action_type: str
    platform: str
    impact: str
    baseline_metrics: dict
    title: Optional[str] = None
    suggested_action: Optional[str] = None
    target_id: Optional[str] = None
    campaign_id: Optional[str] = None
    keyword: Optional[str] = None
    suggested_bid: Optional[float] = None
    adset_id: Optional[str] = None
    normalized_key: Optional[str] = None
    quality_label: Optional[str] = None
    confidence_score: Optional[float] = None
    guardrail_status: Optional[str] = None
    guardrail_reasons: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)
    expected_impact: Optional[str] = None
    manual: bool = False
    status: Optional[str] = None

class EmailSettingsRequest(BaseModel):
    client_name: str
    enabled: bool = False
    recipients: list[str] = []
    frequency: str = "weekly"
    send_day: str = "Monday"
    send_time: str = "08:00"
    timezone: str = "Asia/Kuala_Lumpur"
    subject: str = "Weekly Ad Performance Report - {client_name}"
    message: str = ""
    attachments: dict = {}

def require_api_key(env_name: str, provided_key: str | None):
    expected_key = os.getenv(env_name)
    if not expected_key:
        raise HTTPException(status_code=500, detail=f"{env_name} is not configured")
    if not provided_key or provided_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid API Key")

def days_since_iso(timestamp: str | None):
    if not timestamp:
        return 0
    try:
        applied_at = datetime.fromisoformat(timestamp)
    except ValueError:
        return 0
    return max(0, (datetime.now() - applied_at).days)

def load_json_if_exists(path: Path):
    if not path.exists():
        return None
    with open(path, 'r') as f:
        return json.load(f)

def safe_number(value, default=0):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def summarize_cached_metrics(client_data: dict):
    """Build a compact current-performance snapshot from cached volume data."""
    platforms = {}
    totals = {
        "total_spend": 0.0,
        "total_conversions": 0.0,
        "total_conversion_value": 0.0,
    }

    customer_id = str(client_data.get('customer_id', '')).replace('-', '')
    if customer_id:
        google_data = load_json_if_exists(Path(f"/data/google_ads_metrics_{customer_id}.json"))
        if google_data:
            summary = google_data.get('summary', {})
            spend = safe_number(summary.get('total_cost') or summary.get('total_spend'))
            conversions = safe_number(summary.get('total_conversions'))
            conversion_value = safe_number(summary.get('total_conversion_value'))
            platforms["Google"] = {
                "spend": round(spend, 2),
                "conversions": round(conversions, 2),
                "cpa": round(spend / conversions, 2) if conversions else 0,
                "conversion_value": round(conversion_value, 2),
                "fetched_at": google_data.get('fetched_at'),
                "date_range": google_data.get('date_range'),
            }
            totals["total_spend"] += spend
            totals["total_conversions"] += conversions
            totals["total_conversion_value"] += conversion_value

    facebook_id = str(client_data.get('facebook_ad_account_id', '')).replace('act_', '')
    if facebook_id:
        facebook_data = load_json_if_exists(Path(f"/data/facebook_ads_metrics_{facebook_id}.json"))
        if facebook_data:
            summary = facebook_data.get('summary', {})
            spend = safe_number(summary.get('total_spend'))
            conversions = safe_number(summary.get('total_conversions'))
            conversion_value = safe_number(summary.get('total_conversion_value'))
            platforms["Meta"] = {
                "spend": round(spend, 2),
                "conversions": round(conversions, 2),
                "cpa": round(spend / conversions, 2) if conversions else 0,
                "conversion_value": round(conversion_value, 2),
                "fetched_at": facebook_data.get('fetched_at'),
                "date_range": facebook_data.get('date_range'),
            }
            totals["total_spend"] += spend
            totals["total_conversions"] += conversions
            totals["total_conversion_value"] += conversion_value

    total_spend = totals["total_spend"]
    total_conversions = totals["total_conversions"]
    total_conversion_value = totals["total_conversion_value"]

    return {
        "total_spend": round(total_spend, 2),
        "total_conversions": round(total_conversions, 2),
        "blended_cpa": round(total_spend / total_conversions, 2) if total_conversions else 0,
        "blended_roas": round(total_conversion_value / total_spend, 2) if total_spend else 0,
        "platforms": platforms,
    }

def build_tracking_snapshot(record: dict, client_data: dict, milestone_day: int):
    baseline = record.get("baseline_metrics", {}) or {}
    current = summarize_cached_metrics(client_data)

    baseline_cpa = safe_number(baseline.get("blended_cpa") or baseline.get("current_cpa"))
    current_cpa = safe_number(current.get("blended_cpa"))
    baseline_spend = safe_number(baseline.get("total_spend") or baseline.get("current_spend"))
    current_spend = safe_number(current.get("total_spend"))
    baseline_conversions = safe_number(baseline.get("total_conversions"))
    current_conversions = safe_number(current.get("total_conversions"))

    comparison = {
        "cpa_change_pct": round(((current_cpa - baseline_cpa) / baseline_cpa) * 100, 2) if baseline_cpa else None,
        "spend_change_pct": round(((current_spend - baseline_spend) / baseline_spend) * 100, 2) if baseline_spend else None,
        "conversion_change": round(current_conversions - baseline_conversions, 2),
    }

    if comparison["cpa_change_pct"] is None:
        summary = f"Day {milestone_day} snapshot captured; CPA baseline unavailable."
        outcome_status = "Needs data"
    elif comparison["cpa_change_pct"] < 0:
        summary = f"CPA improved {abs(comparison['cpa_change_pct']):.1f}% by day {milestone_day}."
        outcome_status = "Improved"
    elif comparison["cpa_change_pct"] > 0:
        summary = f"CPA worsened {comparison['cpa_change_pct']:.1f}% by day {milestone_day}."
        outcome_status = "Worse"
    else:
        summary = f"CPA unchanged by day {milestone_day}."
        outcome_status = "Flat"

    return {
        "captured_at": datetime.now().isoformat(),
        "milestone_day": milestone_day,
        "current_metrics": current,
        "comparison": comparison,
        "actual_impact": {
            "status": outcome_status,
            "cpa_change_pct": comparison["cpa_change_pct"],
            "spend_change_pct": comparison["spend_change_pct"],
            "conversion_change": comparison["conversion_change"],
        },
        "summary": summary,
    }

def update_tracking_snapshots_impl():
    tracking_file = Path("/data/tracking.json")
    if not tracking_file.exists():
        return {"updated": 0, "message": "No tracking data found"}

    clients = load_clients()
    with open(tracking_file, 'r') as f:
        tracking_data = json.load(f)

    updated = 0
    changed = False
    for record in tracking_data:
        if record.get("status") != "Tracking":
            continue

        client_data = clients.get(record.get("client_name"), {})
        if not client_data:
            continue

        days_active = days_since_iso(record.get("applied_at"))
        if record.get("days_active") != days_active:
            record["days_active"] = days_active
            changed = True
        snapshots = record.setdefault("snapshots", {})

        for milestone in (7, 14, 30):
            key = f"day_{milestone}"
            if days_active >= milestone and key not in snapshots:
                snapshots[key] = build_tracking_snapshot(record, client_data, milestone)
                updated += 1
                changed = True

        if days_active >= 30 and record.get("status") == "Tracking":
            record["status"] = "Completed"
            changed = True

    if changed:
        with open(tracking_file, 'w') as f:
            json.dump(tracking_data, f, indent=2)
        volume.commit()

    return {"updated": updated}

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("adspulse-api-creds"),
        modal.Secret.from_name("google-ads-creds"),
        modal.Secret.from_name("facebook-ads-creds"),
    ],
    volumes={"/data": volume},
)
@modal.fastapi_endpoint(method="POST", label="api-apply")
def apply_recommendation(request: ApplyRequest, x_api_key: str = Header(None)):
    require_api_key("ADSPULSE_INTERNAL_API_KEY", x_api_key)
    
    tracking_file = Path("/data/tracking.json")
    tracking_data = []
    if tracking_file.exists():
        with open(tracking_file, 'r') as f:
            tracking_data = json.load(f)
    
    request_key = request.normalized_key or normalized_recommendation_key({
        "action_type": request.action_type,
        "platform": request.platform,
        "keyword": request.keyword,
        "target_id": request.target_id or request.adset_id,
        "campaign_id": request.campaign_id,
    })

    # Check if already tracking
    if any(
        t.get('recommendation_id') == request.recommendation_id
        or (request_key and (t.get("normalized_key") == request_key or normalized_recommendation_key(t) == request_key))
        for t in tracking_data
    ):
        return {"status": "already_tracking", "message": "This recommendation is already being tracked."}

    # --- EXECUTION LOGIC ---
    is_dismissal = request.status == "Dismissed"
    execution_status = "Dismissed: user removed recommendation" if is_dismissal else "Manual: recorded"
    response_status = "dismissed" if is_dismissal else ("manual_required" if request.manual else "tracked")
    if is_dismissal or request.manual:
        pass
    elif request.platform == "Google":
        try:
            import google_ads_executor
            
            # Load client data for customer_id
            clients = load_clients()
            client_data = clients.get(request.client_name, {})
            customer_id = client_data.get('customer_id', '').replace('-', '')

            if request.action_type == "add_negative_keyword" and request.campaign_id and request.keyword:
                res = google_ads_executor.add_negative_keyword(customer_id, request.campaign_id, request.keyword)
                execution_status = f"Applied: {res.get('status')}"
                response_status = "applied"
            elif request.action_type == "keyword_action" and request.suggested_action == "PAUSED" and request.target_id:
                res = google_ads_executor.pause_ad_group_criterion(customer_id, request.target_id)
                execution_status = f"Applied: {res.get('status')}"
                response_status = "applied"
            elif request.action_type == "bid_adjustment" and request.target_id and request.suggested_bid:
                res = google_ads_executor.update_bid(customer_id, request.target_id, request.suggested_bid)
                execution_status = f"Applied: {res.get('status')}"
                response_status = "applied"
            else:
                execution_status = "Manual: unsupported Google action"
                response_status = "manual_required"
        except Exception as e:
            print(f"Execution Error: {e}")
            execution_status = f"Error: {str(e)}"
            response_status = "error"
    elif request.platform == "Meta":
        try:
            import meta_ads_executor
            
            if request.action_type in {"budget_adjustment", "budget_scaling"} and request.campaign_id and request.suggested_bid:
                res = meta_ads_executor.update_budget(request.campaign_id, request.suggested_bid)
                execution_status = f"Applied: {res.get('status')}"
                response_status = "applied"
            else:
                execution_status = "Manual: unsupported Meta action"
                response_status = "manual_required"
        except Exception as e:
            print(f"Meta Execution Error: {e}")
            execution_status = f"Meta Error: {str(e)}"
            response_status = "error"
    # -----------------------

    # Record the implementation
    new_record = {
        "recommendation_id": request.recommendation_id,
        "normalized_key": request_key,
        "client_name": request.client_name,
        "action_type": request.action_type,
        "platform": request.platform,
        "impact": request.impact,
        "quality_label": request.quality_label,
        "confidence_score": request.confidence_score,
        "guardrail_status": request.guardrail_status,
        "guardrail_reasons": request.guardrail_reasons,
        "evidence_snapshot": request.evidence,
        "expected_impact": request.expected_impact,
        "title": request.title,
        "applied_at": datetime.now().isoformat(),
        "baseline_metrics": request.baseline_metrics,
        "suggested_action": request.suggested_action,
        "target_id": request.target_id,
        "campaign_id": request.campaign_id,
        "adset_id": request.adset_id,
        "keyword": request.keyword,
        "suggested_bid": request.suggested_bid,
        "execution_status": execution_status,
        "status": "Dismissed" if is_dismissal else ("Tracking" if response_status != "error" else "Failed"),
        "days_active": 0,
        "snapshots": {
            "day_0": {
                "captured_at": datetime.now().isoformat(),
                "baseline_metrics": request.baseline_metrics,
                "expected_impact": request.expected_impact or request.baseline_metrics.get("expected_outcome"),
                "evidence": request.evidence,
            }
        }
    }
    
    tracking_data.append(new_record)
    
    with open(tracking_file, 'w') as f:
        json.dump(tracking_data, f, indent=2)
    volume.commit()
    
    return {"status": response_status, "execution_status": execution_status}

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("adspulse-api-creds")],
    volumes={"/data": volume},
)
@modal.fastapi_endpoint(method="GET", label="api-tracking")
def get_tracking_data(client_name: str, x_api_key: str = Header(None)):
    require_api_key("ADSPULSE_INTERNAL_API_KEY", x_api_key)
    
    tracking_file = Path("/data/tracking.json")
    if not tracking_file.exists():
        return []
    
    with open(tracking_file, 'r') as f:
        tracking_data = json.load(f)
    
    client_items = [t for t in tracking_data if t['client_name'] == client_name]
    for item in client_items:
        item['days_active'] = days_since_iso(item.get('applied_at'))
        if item.get('days_active', 0) >= 30 and item.get('status') == 'Tracking':
            item['status'] = 'Completed'
    return client_items

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("adspulse-api-creds")],
    volumes={"/data": volume},
)
@modal.fastapi_endpoint(method="DELETE", label="api-tracking-delete")
def delete_tracked_item(recommendation_id: str, client_name: str, x_api_key: str = Header(None)):
    require_api_key("ADSPULSE_INTERNAL_API_KEY", x_api_key)
    
    tracking_file = Path("/data/tracking.json")
    if not tracking_file.exists():
        return {"status": "success", "message": "No tracking data found."}
    
    with open(tracking_file, 'r') as f:
        tracking_data = json.load(f)
    
    # Remove the item
    new_tracking_data = [t for t in tracking_data if t.get('recommendation_id') != recommendation_id or t.get('client_name') != client_name]
    
    with open(tracking_file, 'w') as f:
        json.dump(new_tracking_data, f, indent=2)
    volume.commit()
    
    return {"status": "success", "message": "Item removed from tracking."}

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("adspulse-api-creds")],
    volumes={"/data": volume},
)
@modal.fastapi_endpoint(method="GET", label="api-email-settings")
def get_email_settings(client_name: str, x_api_key: str = Header(None)):
    require_api_key("ADSPULSE_INTERNAL_API_KEY", x_api_key)
    volume.reload()

    clients = load_clients()
    client_data = clients.get(client_name)
    if not client_data:
        return JSONResponse(status_code=404, content={"error": "Client not found"})

    return {
        "client_name": client_name,
        "settings": normalize_email_settings(client_name, client_data),
        "delivery": {
            "scheduler": "Modal hourly email dispatcher",
            "status": "active when deployed",
        },
    }

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("adspulse-api-creds")],
    volumes={"/data": volume},
)
@modal.fastapi_endpoint(method="POST", label="api-email-settings-update")
def update_email_settings(request: EmailSettingsRequest, x_api_key: str = Header(None)):
    require_api_key("ADSPULSE_INTERNAL_API_KEY", x_api_key)
    volume.reload()

    clients = load_clients()
    client_data = clients.get(request.client_name)
    if not client_data:
        return JSONResponse(status_code=404, content={"error": "Client not found"})

    recipients = parse_email_recipients(request.recipients)
    if request.enabled and not recipients:
        return JSONResponse(status_code=400, content={"error": "At least one recipient is required when email reports are enabled"})

    settings = {
        "enabled": bool(request.enabled),
        "recipients": recipients,
        "frequency": request.frequency if request.frequency in {"daily", "weekly", "monthly"} else "weekly",
        "send_day": request.send_day,
        "send_time": request.send_time,
        "timezone": request.timezone or "Asia/Kuala_Lumpur",
        "subject": request.subject or "Weekly Ad Performance Report - {client_name}",
        "message": request.message or default_email_settings(request.client_name, client_data)["message"],
        "attachments": {
            "google_html": bool((request.attachments or {}).get("google_html", True)),
            "meta_html": bool((request.attachments or {}).get("meta_html", True)),
            "summary_csv": bool((request.attachments or {}).get("summary_csv", False)),
        },
    }

    client_data["email"] = ", ".join(recipients)
    client_data["email_reports"] = settings
    clients[request.client_name] = client_data
    save_clients(clients)

    return {
        "client_name": request.client_name,
        "settings": settings,
        "status": "saved",
    }

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("adspulse-api-creds"),
        modal.Secret.from_name("google-ads-creds"),
        modal.Secret.from_name("facebook-ads-creds"),
    ],
    volumes={"/data": volume},
)
@modal.fastapi_endpoint(method="GET", label="api-dashboard")
def get_dashboard_data(client_name: str, start_date: str = None, end_date: str = None, x_api_key: str = Header(None)):
    require_api_key("ADSPULSE_INTERNAL_API_KEY", x_api_key)
    
    import glob
    import generate_dashboard_data
    volume.reload()

    requested_range = bool(start_date or end_date)
    if requested_range:
        if not start_date or not end_date:
            return JSONResponse(status_code=400, content={"error": "Both start_date and end_date are required"})
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Dates must use YYYY-MM-DD format"})
        if start_date > end_date:
            return JSONResponse(status_code=400, content={"error": "start_date must be before or equal to end_date"})
    
    # Prioritize volume files for this client
    # Find client ID from clients.json
    clients = load_clients()
    client_data = clients.get(client_name, {})
    if not client_data:
        return JSONResponse(status_code=404, content={"error": "Client not found"})

    g_id = client_data.get('customer_id', '').replace('-', '')
    
    metrics_files = glob.glob(f'/data/google_ads_metrics_{g_id}.json')
    if not metrics_files:
        return JSONResponse(status_code=404, content={"error": "No data found. Sync required."})
    
    latest_metrics = max(metrics_files, key=os.path.getmtime)
    recs_file = latest_metrics.replace('metrics', 'recommendations')
    
    try:
        with open(latest_metrics, 'r') as f:
            google_data = json.load(f)

        data = generate_dashboard_data.generate_dashboard_data(latest_metrics, recs_file, '/tmp/db.json')
        data['client_name'] = client_name
        data['account_name'] = client_data.get('account_name') or client_data.get('description') or client_name
        data['customer_id'] = client_data.get('customer_id')
        data['facebook_ad_account_id'] = client_data.get('facebook_ad_account_id')

        filtered_from_daily = False
        if requested_range:
            requested_date_range = {
                "start_date": start_date,
                "end_date": end_date,
                "days": date_range_days(start_date, end_date)
            }
            google_range = google_data.get('date_range')
            if range_matches(google_range, start_date, end_date):
                data['date_range'] = requested_date_range
            elif google_data.get('campaign_daily') and range_is_covered(google_range, start_date, end_date):
                data['campaigns'] = aggregate_google_daily(
                    google_data.get('campaign_daily', []),
                    start_date,
                    end_date
                )
                data['date_range'] = requested_date_range
                filtered_from_daily = True
            else:
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": "Selected date range is not available in the fast cache yet. Run a sync that covers this range.",
                        "available_range": google_range,
                    }
                )

        if requested_range:
            data['trends'] = google_trends_from_daily(
                google_data.get('campaign_daily', []),
                start_date,
                end_date,
            )
        else:
            google_range = google_data.get('date_range')
            if google_range and google_data.get('campaign_daily'):
                data['trends'] = google_trends_from_daily(
                    google_data.get('campaign_daily', []),
                    google_range.get('start_date'),
                    google_range.get('end_date'),
                )
            else:
                data['trends'] = None

        data['platform_date_ranges'] = {
            'google': data.get('date_range')
        }
        
        # --- Inject Facebook Data if available ---
        fb_id = client_data.get('facebook_ad_account_id', '').replace('act_', '')
        fb_metrics_files = glob.glob(f'/data/facebook_ads_metrics_{fb_id}.json')

        if fb_metrics_files:
            latest_fb = max(fb_metrics_files, key=os.path.getmtime)
            fb_recs_file = latest_fb.replace('metrics', 'recommendations')
            try:
                with open(latest_fb, 'r') as f:
                    fb_data = json.load(f)
                fb_range = fb_data.get('date_range')
                
                # Merge Facebook campaigns
                if requested_range:
                    if range_matches(fb_range, start_date, end_date):
                        fb_campaigns = fb_data.get('campaigns', [])
                        data['platform_date_ranges']['meta'] = requested_date_range
                    elif fb_data.get('campaign_daily') and range_is_covered(fb_range, start_date, end_date):
                        campaign_lookup = {
                            c.get('campaign_id'): c
                            for c in fb_data.get('campaigns', [])
                        }
                        fb_campaigns = aggregate_meta_daily(
                            fb_data.get('campaign_daily', []),
                            start_date,
                            end_date,
                            campaign_lookup
                        )
                        data['platform_date_ranges']['meta'] = requested_date_range
                        filtered_from_daily = True
                    else:
                        return JSONResponse(
                            status_code=409,
                            content={
                                "error": "Selected date range is not available in the Meta fast cache yet. Run a sync that covers this range.",
                                "available_range": fb_range,
                            }
                        )
                else:
                    fb_campaigns = fb_data.get('campaigns', [])
                    data['platform_date_ranges']['meta'] = fb_range

                for c in fb_campaigns:
                    c['platform'] = 'Meta'
                data['campaigns'].extend(fb_campaigns)
                
                # Merge Facebook summary into total
                if requested_range:
                    data['summary'] = summarize_campaigns(data.get('campaigns', []))
                else:
                    fb_summary = fb_data.get('summary', {})
                    data['summary']['total_spend'] += fb_summary.get('total_spend', 0)
                    data['summary']['total_conversions'] += fb_summary.get('total_conversions', 0)
                    if data['summary']['total_conversions'] > 0:
                        data['summary']['cost_per_conversion'] = data['summary']['total_spend'] / data['summary']['total_conversions']
                
                # --- Inject Facebook detailed breakdowns ---
                if filtered_from_daily:
                    data['search_queries'] = []
                    data['geo_performance'] = []
                    data['keywords'] = []
                    data['insights'] = []
                    data['ad_sets'] = []
                    data['demographic_breakdown'] = []
                    data['placement_breakdown'] = []
                    data['meta_geo_performance'] = []
                    data['time_performance'] = {}
                else:
                    data['ad_sets'] = fb_data.get('ad_sets', [])
                    data['demographic_breakdown'] = fb_data.get('demographic_breakdown', [])
                    data['placement_breakdown'] = fb_data.get('placement_breakdown', [])
                    data['meta_geo_performance'] = fb_data.get('geo_performance', [])
                    data['time_performance'] = fb_data.get('time_performance', {})
                    
                # Merge recommendations
                if os.path.exists(fb_recs_file):
                    with open(fb_recs_file, 'r') as f:
                        fb_recs = json.load(f)
                    
                    for rec in fb_recs:
                        # Generate a stable ID for Meta recommendations
                        import hashlib
                        m_rec_id_raw = f"meta_{rec.get('action')}_{rec.get('campaign_name')}_{rec.get('reason')}"
                        m_rec_id = hashlib.md5(m_rec_id_raw.encode()).hexdigest()

                        rec_obj = {
                            'id': m_rec_id,
                            'recommendation_id': m_rec_id,
                            'title': f"{rec.get('action', 'Review').replace('_', ' ').title()} {rec.get('campaign_name', '')}".strip(),
                            'description': rec.get('reason', ''),
                            'platform': 'Meta',
                            'impact': 'Medium',
                            'expected_impact': rec.get('expected_impact') or "Review performance before changing budget or targeting.",
                            'action_type': rec.get('type', 'review'),
                            'campaign_name': rec.get('campaign_name'),
                            'adset_name': rec.get('adset_name'),
                            'campaign_id': rec.get('campaign_id'),
                            'adset_id': rec.get('adset_id'),
                            'suggested_bid': rec.get('suggested_budget') or rec.get('impact_data', {}).get('suggested_budget'),
                            'impact_data': rec.get('impact_data') or {},
                            'automation': rec.get('automation') or {},
                        }
                        data['recommendations'].append(rec_obj)
            except Exception as e:
                print(f"Error merging Facebook data: {e}")
        # --- End Inject ---

        if requested_range:
            data['date_range'] = requested_date_range
            data['summary'] = summarize_campaigns(data.get('campaigns', []))
            if filtered_from_daily:
                data['recommendations'] = []

        data = apply_recommendation_guardrails(data)

        # --- Filter out already tracked recommendations ---
        tracking_file = Path("/data/tracking.json")
        if tracking_file.exists():
            with open(tracking_file, 'r') as f:
                tracking_data = json.load(f)

            client_tracking = [
                item for item in tracking_data
                if item.get("client_name") == client_name and item.get("status") != "Failed"
            ]
            tracked_ids = {
                item.get("recommendation_id")
                for item in client_tracking
                if item.get("recommendation_id")
            }
            tracked_match_keys = {
                key for item in client_tracking
                for key in (item.get("normalized_key"), recommendation_match_key(item), recommendation_fallback_key(item))
                if key
            }
            filtered_recommendations = [
                rec for rec in data.get('recommendations', [])
                if (
                    rec.get('recommendation_id') not in tracked_ids
                    and rec.get('id') not in tracked_ids
                    and rec.get('normalized_key') not in tracked_match_keys
                    and recommendation_match_key(rec) not in tracked_match_keys
                    and recommendation_fallback_key(rec) not in tracked_match_keys
                )
            ]
            data['recommendations'] = filtered_recommendations
        # ------------------------------------------------

        return data
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.function(volumes={"/data": volume}, image=image)
def inspect_volume(path: str, query: str = None):
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return f"File {path} not found"
    with open(p, 'r') as f:
        if query:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if query in line:
                    start = max(0, i - 10)
                    end = min(len(lines), i + 20)
                    context = "".join(lines[start:end])
                    print(f"FOUND '{query}' in {path} at line {i+1}:\n{context}")
            return "Search complete"
        else:
            content = f.read()
            print(f"CONTENT OF {path}: {content[:1000]}...")
            return content

@app.function(volumes={"/data": volume}, image=image)
def list_volume(path: str = "/data"):
    import os
    files = os.listdir(path)
    print(f"FILES IN {path}: {files}")
    return files

@app.function(volumes={"/data": volume}, image=image)
def find_in_volume(query: str):
    import os
    results = []
    for root, dirs, files in os.walk("/data"):
        for file in files:
            if file.endswith(".json"):
                path = os.path.join(root, file)
                with open(path, 'r') as f:
                    content = f.read()
                    if query in content:
                        results.append(path)
    return results

@app.local_entrypoint()
def search_volume(query: str):
    res = find_in_volume.remote(query)
    print(f"FOUND '{query}' IN: {res}")

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("adspulse-api-creds"),
        modal.Secret.from_name("google-ads-creds"),
    ],
    volumes={"/data": volume},
)
@modal.fastapi_endpoint(method="POST", label="api-refresh")
async def refresh_data(request: Request, x_api_key: str = Header(None)):
    require_api_key("ADSPULSE_INTERNAL_API_KEY", x_api_key)
        
    body = await request.json()
    client_name = body.get("client_name")
    
    clients = load_clients()
        
    client_data = clients.get(client_name)
    if not client_data:
        return JSONResponse(status_code=404, content={"error": "Client not found"})
        
    try:
        start_date, end_date, days = resolve_report_date_range(
            body.get("days", 30),
            body.get("start_date"),
            body.get("end_date"),
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    generate_client_report.spawn(
        client_name=client_name,
        customer_id=client_data.get('customer_id'),
        facebook_ad_account_id=client_data.get('facebook_ad_account_id'),
        email=TEST_EMAIL,
        send_email=False,
        days=days,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
    )
    
    return {
        "status": "triggered",
        "days": days,
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d'),
    }

@app.function(
    schedule=modal.Cron("0 18 * * *"),  # 2 AM Malaysia Time
    image=image,
    secrets=[
        modal.Secret.from_name("google-ads-creds"),
        modal.Secret.from_name("facebook-ads-creds"),
        modal.Secret.from_name("google-credentials"),
    ],
    volumes={"/data": volume},
    timeout=1800,
)
def scheduled_data_refresh():
    """Refresh cached dashboard data for all configured clients."""
    clients = load_clients()

    for client_name, client_data in clients.items():
        generate_client_report.spawn(
            client_name=client_name,
            customer_id=client_data.get('customer_id'),
            facebook_ad_account_id=client_data.get('facebook_ad_account_id'),
            email=None,
            send_email=False,
            days=90
        )

def email_schedule_due(settings, now):
    if not settings.get("enabled"):
        return False
    if not parse_email_recipients(settings.get("recipients")):
        return False

    send_time = settings.get("send_time", "08:00")
    try:
        send_hour = int(send_time.split(":")[0])
    except (ValueError, IndexError):
        send_hour = 8
    if now.hour != send_hour:
        return False

    frequency = settings.get("frequency", "weekly")
    if frequency == "daily":
        return True
    if frequency == "weekly":
        return now.strftime("%A").lower() == str(settings.get("send_day", "Monday")).lower()
    if frequency == "monthly":
        try:
            send_day = int(settings.get("send_day", "1"))
        except (TypeError, ValueError):
            send_day = 1
        return now.day == max(1, min(send_day, 28))
    return False

@app.function(
    schedule=modal.Cron("0 * * * *"),
    image=image,
    secrets=[
        modal.Secret.from_name("google-ads-creds"),
        modal.Secret.from_name("facebook-ads-creds"),
        modal.Secret.from_name("google-credentials"),
    ],
    volumes={"/data": volume},
    timeout=1800,
)
def scheduled_email_reports():
    """Send configured email reports when a client's saved schedule is due."""
    from zoneinfo import ZoneInfo

    volume.reload()
    clients = load_clients()
    log_file = Path("/data/email_delivery_log.json")
    if log_file.exists():
        with open(log_file, "r") as f:
            delivery_log = json.load(f)
    else:
        delivery_log = {}

    sent = 0
    for client_name, client_data in clients.items():
        settings = normalize_email_settings(client_name, client_data)
        timezone = settings.get("timezone") or "Asia/Kuala_Lumpur"
        try:
            now = datetime.now(ZoneInfo(timezone))
        except Exception:
            now = datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))

        if not email_schedule_due(settings, now):
            continue

        log_key = f"{client_name}:{now.strftime('%Y-%m-%d')}:{now.hour:02d}"
        if delivery_log.get(log_key):
            continue

        recipients = parse_email_recipients(settings.get("recipients"))
        generate_client_report.spawn(
            client_name=client_name,
            customer_id=client_data.get('customer_id'),
            facebook_ad_account_id=client_data.get('facebook_ad_account_id'),
            email=", ".join(recipients),
            send_email=True,
            days=30,
            email_settings=settings,
        )
        delivery_log[log_key] = {
            "queued_at": datetime.now().isoformat(),
            "recipients": recipients,
            "frequency": settings.get("frequency"),
        }
        sent += 1

    if sent:
        with open(log_file, "w") as f:
            json.dump(delivery_log, f, indent=2)
        volume.commit()

    return {"queued": sent}

@app.function(
    schedule=modal.Cron("0 19 * * *"),  # 3 AM Malaysia Time, after data refresh
    image=image,
    volumes={"/data": volume},
    timeout=300,
)
def scheduled_tracking_snapshots():
    """Capture Day 7/14/30 outcome snapshots for tracked recommendations."""
    return update_tracking_snapshots_impl()

@app.function(
    image=image,
    volumes={"/data": volume},
    timeout=300,
)
def update_tracking_snapshots():
    """Manual trigger for tracking snapshot updates."""
    return update_tracking_snapshots_impl()

@app.local_entrypoint()
def update_tracking_now():
    result = update_tracking_snapshots.remote()
    print(result)
