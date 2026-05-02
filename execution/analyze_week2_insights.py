#!/usr/bin/env python3
"""
Week 2 Quick Wins - Advanced Analysis Functions
Includes: Budget Pacing, Device Performance, Landing Page Heatmap
"""

import json
from datetime import datetime, timedelta
from collections import defaultdict


def analyze_budget_pacing(metrics_data, monthly_budget=None):
    """
    Analyze budget pacing and forecast end-of-month spend.

    Args:
        metrics_data: Google Ads metrics data
        monthly_budget: Optional monthly budget target

    Returns:
        Dict with pacing analysis and alerts
    """
    summary = metrics_data.get('summary', {})
    date_range = metrics_data.get('date_range', {})

    total_spend = summary.get('total_cost', 0)
    start_date = datetime.strptime(date_range.get('start_date', ''), '%Y-%m-%d')
    end_date = datetime.strptime(date_range.get('end_date', ''), '%Y-%m-%d')

    days_in_period = (end_date - start_date).days + 1
    daily_avg_spend = total_spend / days_in_period if days_in_period > 0 else 0

    # Calculate monthly projections
    now = datetime.now()
    days_in_month = (datetime(now.year, now.month % 12 + 1, 1) - timedelta(days=1)).day
    days_elapsed = now.day
    days_remaining = days_in_month - days_elapsed

    projected_monthly_spend = daily_avg_spend * days_in_month

    pacing_analysis = {
        "daily_avg_spend": daily_avg_spend,
        "days_in_period": days_in_period,
        "projected_monthly_spend": projected_monthly_spend,
        "days_elapsed_this_month": days_elapsed,
        "days_remaining_this_month": days_remaining,
        "alerts": []
    }

    if monthly_budget:
        pacing_analysis["monthly_budget"] = monthly_budget
        target_daily_spend = monthly_budget / days_in_month
        pacing_analysis["target_daily_spend"] = target_daily_spend

        # Calculate variance
        spend_variance_pct = ((daily_avg_spend - target_daily_spend) / target_daily_spend * 100) if target_daily_spend > 0 else 0
        pacing_analysis["spend_variance_pct"] = spend_variance_pct

        # Budget utilization
        current_month_spend_estimate = daily_avg_spend * days_elapsed
        budget_utilization = (current_month_spend_estimate / monthly_budget * 100) if monthly_budget > 0 else 0
        pacing_analysis["budget_utilization_pct"] = budget_utilization

        # Projected end date if continuing at current pace
        if daily_avg_spend > 0:
            days_until_budget_depleted = monthly_budget / daily_avg_spend
            pacing_analysis["days_until_budget_depleted"] = days_until_budget_depleted

        # Generate alerts
        if spend_variance_pct > 20:
            pacing_analysis["alerts"].append({
                "severity": "HIGH",
                "message": f"Spending {spend_variance_pct:.0f}% faster than target. Budget may run out by day {int(days_until_budget_depleted)}.",
                "recommendation": "Consider reducing bids or pausing low-performing campaigns"
            })
        elif spend_variance_pct < -20:
            pacing_analysis["alerts"].append({
                "severity": "MEDIUM",
                "message": f"Spending {abs(spend_variance_pct):.0f}% slower than target. May underutilize budget.",
                "recommendation": "Consider increasing bids on top performers or expanding keywords"
            })

        if projected_monthly_spend > monthly_budget:
            overspend = projected_monthly_spend - monthly_budget
            pacing_analysis["alerts"].append({
                "severity": "WARNING",
                "message": f"Projected to exceed budget by RM {overspend:.2f} ({(overspend/monthly_budget*100):.0f}%)",
                "recommendation": "Reduce daily spend to RM {:.2f}".format(monthly_budget / days_in_month)
            })

    return pacing_analysis


def analyze_device_performance(campaigns, keywords):
    """
    Analyze performance by device type.
    Note: Device data requires segment fetch - this analyzes what we can from existing data.

    Returns placeholder structure for when device-segmented data is available.
    """
    # This is a placeholder - real device data needs to be fetched with segments
    return {
        "note": "Device segmentation requires additional API fetch with segments.device",
        "recommendation": "Will be implemented when device-segmented data is added to fetch script",
        "placeholder_insight": "Mobile typically accounts for 60-70% of chiropractic searches. Consider mobile-first strategy."
    }


def analyze_landing_page_performance(keywords, ads):
    """
    Create landing page performance heatmap.
    Maps landing pages to conversion rates and identifies mismatches.
    """
    # Group keywords by their landing page
    landing_pages = defaultdict(lambda: {
        'keywords': [],
        'total_clicks': 0,
        'total_cost': 0,
        'total_conversions': 0,
        'total_impressions': 0
    })

    # Extract landing page URLs from ads and map to keywords
    ad_group_urls = {}
    for ad in ads:
        ad_group_id = ad.get('ad_group_id')
        final_url = ad.get('final_urls', [''])[0] if ad.get('final_urls') else 'Unknown'
        if ad_group_id and final_url:
            ad_group_urls[ad_group_id] = final_url

    # Aggregate keyword data by landing page
    for kw in keywords:
        ad_group_id = kw.get('ad_group_id')
        landing_url = ad_group_urls.get(ad_group_id, 'Unknown')

        landing_pages[landing_url]['keywords'].append(kw['keyword_text'])
        landing_pages[landing_url]['total_clicks'] += kw.get('clicks', 0)
        landing_pages[landing_url]['total_cost'] += kw.get('cost', 0)
        landing_pages[landing_url]['total_conversions'] += kw.get('conversions', 0)
        landing_pages[landing_url]['total_impressions'] += kw.get('impressions', 0)

    # Calculate conversion rates and identify issues
    heatmap = []
    for url, data in landing_pages.items():
        conversion_rate = (data['total_conversions'] / data['total_clicks'] * 100) if data['total_clicks'] > 0 else 0
        cost_per_conversion = (data['total_cost'] / data['total_conversions']) if data['total_conversions'] > 0 else 0

        heatmap.append({
            'landing_page': url,
            'keywords_count': len(data['keywords']),
            'sample_keywords': data['keywords'][:5],
            'clicks': data['total_clicks'],
            'conversions': data['total_conversions'],
            'cost': data['total_cost'],
            'conversion_rate': conversion_rate,
            'cost_per_conversion': cost_per_conversion
        })

    # Sort by cost (highest spend first)
    heatmap.sort(key=lambda x: x['cost'], reverse=True)

    # Identify issues
    issues = []

    # Issue 1: Homepage overuse (detect actual homepage URLs like example.com/ or example.com)
    homepage_pages = []
    for p in heatmap:
        url = p['landing_page'].lower()
        # Check if it's a homepage: domain with just / or no path
        if 'homepage' in url or url.count('/') <= 3:  # e.g., https://domain.com/ has 3 slashes
            # More specific: check if there's no path after domain
            if url.endswith('.com/') or url.endswith('.my/') or url.endswith('.net/') or url.endswith('.org/'):
                homepage_pages.append(p)

    if homepage_pages:
        total_homepage_keywords = sum(p['keywords_count'] for p in homepage_pages)
        if total_homepage_keywords > 10:
            issues.append({
                "issue": "Homepage Overuse",
                "severity": "HIGH",
                "description": f"{total_homepage_keywords} keywords pointing to homepage instead of specific landing pages",
                "impact": "Poor Quality Score (Landing Page Experience), lower conversion rates",
                "recommendation": "Create dedicated landing pages for each ad group theme"
            })

    # Issue 2: Low conversion rate pages
    low_conv_pages = [p for p in heatmap if p['clicks'] > 20 and p['conversion_rate'] < 3]
    if low_conv_pages:
        issues.append({
            "issue": "Low Converting Landing Pages",
            "severity": "MEDIUM",
            "pages": [p['landing_page'] for p in low_conv_pages[:3]],
            "description": f"{len(low_conv_pages)} landing pages with < 3% conversion rate despite traffic",
            "recommendation": "Optimize page content, improve page speed, add clear CTAs"
        })

    # Issue 3: Multiple keywords per page (good) vs single keyword (might indicate missing pages)
    single_keyword_pages = [p for p in heatmap if p['keywords_count'] == 1 and p['clicks'] > 10]
    if len(single_keyword_pages) > 5:
        issues.append({
            "issue": "Potential Landing Page Gaps",
            "severity": "LOW",
            "description": f"{len(single_keyword_pages)} landing pages with only 1 keyword - might need theme consolidation",
            "recommendation": "Review if these keywords could share landing pages or need dedicated pages"
        })

    return {
        "heatmap": heatmap[:10],  # Top 10 by spend
        "total_landing_pages": len(heatmap),
        "issues": issues,
        "summary": {
            "best_performing_page": heatmap[0]['landing_page'] if heatmap else None,
            "best_conversion_rate": max([p['conversion_rate'] for p in heatmap]) if heatmap else 0,
            "worst_conversion_rate": min([p['conversion_rate'] for p in heatmap if p['clicks'] > 10]) if heatmap else 0
        }
    }


def analyze_geo_performance(geo_data, campaign_ids=None):
    """
    Analyze geographic performance data.
    Identifies best/worst locations, opportunities, and waste.

    Args:
        geo_data: List of geographic performance records from Google Ads API
        campaign_ids: List of campaign IDs to apply recommendations to (optional)

    Returns:
        Dict with location analysis, top/bottom performers, and recommendations
    """
    if not geo_data:
        return {
            "note": "No geographic data available",
            "total_locations": 0,
            "top_locations": [],
            "issues": [],
            "recommendations": []
        }

    # Location criterion ID to name mapping (Malaysia-focused for YCK)
    LOCATION_NAMES = {
        2458: "Malaysia",
        1015117: "Kuala Lumpur",
        1015118: "Selangor",
        1015134: "Johor",
        1015128: "Penang",
        1015119: "Perak",
        # Add more as needed
    }

    # Aggregate by location
    location_stats = defaultdict(lambda: {
        'impressions': 0,
        'clicks': 0,
        'cost': 0,
        'conversions': 0,
        'campaigns': set()
    })

    for record in geo_data:
        loc_id = record.get('country_criterion_id')
        if not loc_id:
            continue

        location_stats[loc_id]['impressions'] += record.get('impressions', 0)
        location_stats[loc_id]['clicks'] += record.get('clicks', 0)
        location_stats[loc_id]['cost'] += record.get('cost', 0)
        location_stats[loc_id]['conversions'] += record.get('conversions', 0)
        location_stats[loc_id]['campaigns'].add(record.get('campaign_name', ''))

    # Calculate metrics per location
    locations = []
    for loc_id, stats in location_stats.items():
        location_name = LOCATION_NAMES.get(loc_id, f"Location {loc_id}")
        ctr = (stats['clicks'] / stats['impressions'] * 100) if stats['impressions'] > 0 else 0
        conv_rate = (stats['conversions'] / stats['clicks'] * 100) if stats['clicks'] > 0 else 0
        cpa = (stats['cost'] / stats['conversions']) if stats['conversions'] > 0 else 0

        locations.append({
            'location_id': loc_id,
            'location_name': location_name,
            'impressions': stats['impressions'],
            'clicks': stats['clicks'],
            'cost': stats['cost'],
            'conversions': stats['conversions'],
            'ctr': ctr,
            'conversion_rate': conv_rate,
            'cost_per_conversion': cpa,
            'campaign_count': len(stats['campaigns'])
        })

    # Sort by cost (highest spend first)
    locations.sort(key=lambda x: x['cost'], reverse=True)

    # Identify top performers (good CPA, good conversion rate)
    top_locations = [
        loc for loc in locations
        if loc['conversions'] >= 2 and loc['cost_per_conversion'] < 20
    ][:5]

    # Identify issues
    issues = []
    recommendations = []

    # Issue 1: High spend, low/zero conversions
    wasted_locations = [
        loc for loc in locations
        if loc['cost'] > 50 and loc['conversions'] == 0
    ]

    if wasted_locations:
        total_waste = sum(loc['cost'] for loc in wasted_locations)
        issues.append({
            "issue": "Geographic Waste",
            "severity": "HIGH",
            "locations": [loc['location_name'] for loc in wasted_locations[:3]],
            "description": f"{len(wasted_locations)} location(s) with zero conversions despite RM {total_waste:.2f} spend",
            "recommendation": "Consider excluding these locations or reducing bids significantly"
        })

        for loc in wasted_locations[:2]:
            recommendations.append({
                "type": "geo_exclusion",
                "location": loc['location_name'],
                "campaign_ids": campaign_ids or [],
                "reason": f"RM {loc['cost']:.2f} spent with 0 conversions",
                "expected_impact": f"Save RM {loc['cost'] * 4:.0f}/month"
            })

    # Issue 2: High CPA locations
    expensive_locations = [
        loc for loc in locations
        if loc['conversions'] > 0 and loc['cost_per_conversion'] > 30
    ]

    if expensive_locations:
        issues.append({
            "issue": "High CPA Locations",
            "severity": "MEDIUM",
            "locations": [loc['location_name'] for loc in expensive_locations[:3]],
            "description": f"{len(expensive_locations)} location(s) with CPA > RM 30",
            "recommendation": "Reduce bids by 30-40% in these locations or improve targeting"
        })

        for loc in expensive_locations[:2]:
            recommendations.append({
                "type": "geo_bid_adjustment",
                "location": loc['location_name'],
                "campaign_ids": campaign_ids or [],
                "current_cpa": loc['cost_per_conversion'],
                "suggested_adjustment": "-35%",
                "reason": f"CPA of RM {loc['cost_per_conversion']:.2f} is above target",
                "expected_impact": "Reduce CPA to RM {:.2f}".format(loc['cost_per_conversion'] * 0.7)
            })

    # Opportunity: Low CPA locations to scale
    scale_opportunities = [
        loc for loc in locations
        if loc['conversions'] >= 2 and loc['cost_per_conversion'] < 12 and loc['conversion_rate'] > 5
    ]

    if scale_opportunities:
        for loc in scale_opportunities[:2]:
            recommendations.append({
                "type": "geo_bid_adjustment",
                "location": loc['location_name'],
                "campaign_ids": campaign_ids or [],
                "current_cpa": loc['cost_per_conversion'],
                "suggested_adjustment": "+25%",
                "reason": f"Strong performer: {loc['conversions']:.0f} conversions at RM {loc['cost_per_conversion']:.2f} CPA, {loc['conversion_rate']:.1f}% conv rate",
                "expected_impact": f"Potentially {int(loc['conversions'] * 0.25)} more conversions/week"
            })

    return {
        "total_locations": len(locations),
        "locations": locations[:10],  # Top 10 by spend
        "top_performers": top_locations,
        "issues": issues,
        "recommendations": recommendations,
        "summary": {
            "best_location": top_locations[0]['location_name'] if top_locations else None,
            "best_cpa": min([loc['cost_per_conversion'] for loc in top_locations]) if top_locations else 0,
            "total_spend": sum(loc['cost'] for loc in locations),
            "total_conversions": sum(loc['conversions'] for loc in locations)
        }
    }


def analyze_time_performance(time_data, campaign_ids=None):
    """
    Analyze performance by hour of day and day of week.
    Identifies best/worst times, wasted spend during low-performing hours, and schedule opportunities.

    Args:
        time_data: List of time-segmented performance records from Google Ads API
        campaign_ids: List of campaign IDs to apply recommendations to (optional)

    Returns:
        Dict with hour/day analysis, top/bottom performers, and schedule recommendations
    """
    if not time_data:
        return {
            "note": "No time-segmented data available",
            "hourly_performance": [],
            "daily_performance": [],
            "issues": [],
            "recommendations": []
        }

    # Day of week mapping
    DAY_NAMES = {
        "MONDAY": "Monday",
        "TUESDAY": "Tuesday",
        "WEDNESDAY": "Wednesday",
        "THURSDAY": "Thursday",
        "FRIDAY": "Friday",
        "SATURDAY": "Saturday",
        "SUNDAY": "Sunday"
    }

    # Aggregate by hour (0-23)
    hourly_stats = defaultdict(lambda: {
        'impressions': 0,
        'clicks': 0,
        'cost': 0,
        'conversions': 0
    })

    # Aggregate by day of week
    daily_stats = defaultdict(lambda: {
        'impressions': 0,
        'clicks': 0,
        'cost': 0,
        'conversions': 0
    })

    for record in time_data:
        hour = record.get('hour', 0)
        day = record.get('day_of_week', 'UNKNOWN')

        # Hourly aggregation
        hourly_stats[hour]['impressions'] += record.get('impressions', 0)
        hourly_stats[hour]['clicks'] += record.get('clicks', 0)
        hourly_stats[hour]['cost'] += record.get('cost', 0)
        hourly_stats[hour]['conversions'] += record.get('conversions', 0)

        # Daily aggregation
        daily_stats[day]['impressions'] += record.get('impressions', 0)
        daily_stats[day]['clicks'] += record.get('clicks', 0)
        daily_stats[day]['cost'] += record.get('cost', 0)
        daily_stats[day]['conversions'] += record.get('conversions', 0)

    # Calculate hourly metrics
    hourly_performance = []
    for hour in range(24):
        stats = hourly_stats.get(hour, {'impressions': 0, 'clicks': 0, 'cost': 0, 'conversions': 0})
        ctr = (stats['clicks'] / stats['impressions'] * 100) if stats['impressions'] > 0 else 0
        conv_rate = (stats['conversions'] / stats['clicks'] * 100) if stats['clicks'] > 0 else 0
        cpa = (stats['cost'] / stats['conversions']) if stats['conversions'] > 0 else 0

        hourly_performance.append({
            'hour': hour,
            'hour_label': f"{hour:02d}:00",
            'impressions': stats['impressions'],
            'clicks': stats['clicks'],
            'cost': stats['cost'],
            'conversions': stats['conversions'],
            'ctr': ctr,
            'conversion_rate': conv_rate,
            'cost_per_conversion': cpa
        })

    # Calculate daily metrics
    daily_performance = []
    for day_key, day_name in DAY_NAMES.items():
        stats = daily_stats.get(day_key, {'impressions': 0, 'clicks': 0, 'cost': 0, 'conversions': 0})
        ctr = (stats['clicks'] / stats['impressions'] * 100) if stats['impressions'] > 0 else 0
        conv_rate = (stats['conversions'] / stats['clicks'] * 100) if stats['clicks'] > 0 else 0
        cpa = (stats['cost'] / stats['conversions']) if stats['conversions'] > 0 else 0

        daily_performance.append({
            'day': day_name,
            'impressions': stats['impressions'],
            'clicks': stats['clicks'],
            'cost': stats['cost'],
            'conversions': stats['conversions'],
            'ctr': ctr,
            'conversion_rate': conv_rate,
            'cost_per_conversion': cpa
        })

    # Sort hourly by hour
    hourly_performance.sort(key=lambda x: x['hour'])

    # Sort daily by conversions (best first)
    daily_performance.sort(key=lambda x: x['conversions'], reverse=True)

    # Identify issues and recommendations
    issues = []
    recommendations = []

    # Issue 1: Wasted hours (high spend, zero conversions)
    wasted_hours = [
        h for h in hourly_performance
        if h['cost'] > 20 and h['conversions'] == 0
    ]

    if wasted_hours:
        total_waste = sum(h['cost'] for h in wasted_hours)
        hours_list = [h['hour_label'] for h in wasted_hours[:5]]
        issues.append({
            "issue": "Wasted Spend in Low-Performing Hours",
            "severity": "HIGH",
            "hours": hours_list,
            "description": f"{len(wasted_hours)} hour(s) with zero conversions despite RM {total_waste:.2f} spend",
            "recommendation": "Reduce bids by 50-70% during these hours or pause ads completely"
        })

        for h in wasted_hours[:3]:
            recommendations.append({
                "type": "schedule_bid_adjustment",
                "time_slot": f"{h['hour_label']}",
                "campaign_ids": campaign_ids or [],
                "current_spend": h['cost'],
                "suggested_adjustment": "-70%",
                "reason": f"RM {h['cost']:.2f} spent with 0 conversions during this hour",
                "expected_impact": f"Save RM {h['cost'] * 4 * 0.7:.0f}/month"
            })

    # Issue 2: Low-performing days
    wasted_days = [
        d for d in daily_performance
        if d['cost'] > 50 and d['conversions'] == 0
    ]

    if wasted_days:
        for d in wasted_days[:2]:
            recommendations.append({
                "type": "schedule_bid_adjustment",
                "time_slot": d['day'],
                "campaign_ids": campaign_ids or [],
                "current_spend": d['cost'],
                "suggested_adjustment": "-50%",
                "reason": f"RM {d['cost']:.2f} spent with 0 conversions on {d['day']}s",
                "expected_impact": f"Save RM {d['cost'] * 4 * 0.5:.0f}/month"
            })

    # Opportunity: High-performing hours to scale
    top_hours = [
        h for h in hourly_performance
        if h['conversions'] >= 2 and h['cost_per_conversion'] < 15 and h['conversion_rate'] > 5
    ]

    if top_hours:
        for h in top_hours[:3]:
            recommendations.append({
                "type": "schedule_bid_adjustment",
                "time_slot": f"{h['hour_label']}",
                "campaign_ids": campaign_ids or [],
                "current_performance": f"{h['conversions']:.0f} conv at RM {h['cost_per_conversion']:.2f} CPA",
                "suggested_adjustment": "+30%",
                "reason": f"Strong performer: {h['conversion_rate']:.1f}% conv rate during this hour",
                "expected_impact": f"Potentially {max(1, int(h['conversions'] * 0.3))} more conversions/week"
            })

    # Opportunity: High-performing days to scale
    top_days = [
        d for d in daily_performance
        if d['conversions'] >= 5 and d['cost_per_conversion'] < 20 and d['conversion_rate'] > 4
    ]

    if top_days:
        for d in top_days[:2]:
            recommendations.append({
                "type": "schedule_bid_adjustment",
                "time_slot": d['day'],
                "campaign_ids": campaign_ids or [],
                "current_performance": f"{d['conversions']:.0f} conv at RM {d['cost_per_conversion']:.2f} CPA",
                "suggested_adjustment": "+25%",
                "reason": f"Strong day: {d['conversion_rate']:.1f}% conv rate on {d['day']}s",
                "expected_impact": f"Potentially {max(1, int(d['conversions'] * 0.25))} more conversions/week"
            })

    # Find best and worst performing times
    hours_with_conversions = [h for h in hourly_performance if h['conversions'] > 0]
    best_hour = max(hours_with_conversions, key=lambda x: x['conversion_rate']) if hours_with_conversions else None
    worst_hour = min([h for h in hourly_performance if h['clicks'] > 10], key=lambda x: x['conversion_rate'], default=None)

    days_with_conversions = [d for d in daily_performance if d['conversions'] > 0]
    best_day = max(days_with_conversions, key=lambda x: x['conversion_rate']) if days_with_conversions else None

    return {
        "hourly_performance": hourly_performance,
        "daily_performance": daily_performance,
        "issues": issues,
        "recommendations": recommendations,
        "summary": {
            "best_hour": best_hour['hour_label'] if best_hour else None,
            "best_hour_conv_rate": best_hour['conversion_rate'] if best_hour else 0,
            "worst_hour": worst_hour['hour_label'] if worst_hour else None,
            "worst_hour_conv_rate": worst_hour['conversion_rate'] if worst_hour else 0,
            "best_day": best_day['day'] if best_day else None,
            "best_day_conv_rate": best_day['conversion_rate'] if best_day else 0,
            "total_time_slots_analyzed": len([h for h in hourly_performance if h['impressions'] > 0])
        }
    }
