#!/usr/bin/env python3
"""
Facebook/Meta Ads analysis functions.

Provides Facebook-specific analysis equivalent to the Google Ads
analyze_advanced_insights.py and analyze_week2_insights.py.
"""

from collections import defaultdict


def analyze_audience_performance(demographics, placements):
    """
    Identify wasted spend on poor-performing audience segments and placements.

    Equivalent to Google Ads search query analysis - finds where money is
    being spent without results.
    """
    wasted_segments = []
    top_segments = []

    # Analyze demographic segments
    for seg in demographics:
        spend = seg.get('spend', 0)
        conversions = seg.get('conversions', 0)
        clicks = seg.get('clicks', 0)
        ctr = seg.get('ctr', 0)

        label = f"{seg.get('gender', '').title()} {seg.get('age', '')}"

        if spend > 5 and conversions == 0:
            wasted_segments.append({
                'segment': label,
                'type': 'demographic',
                'spend': spend,
                'clicks': clicks,
                'ctr': ctr,
                'issue': 'Zero conversions',
            })
        elif conversions > 0:
            cpa = spend / conversions
            top_segments.append({
                'segment': label,
                'type': 'demographic',
                'spend': spend,
                'conversions': conversions,
                'cpa': cpa,
                'ctr': ctr,
            })

    # Analyze placement segments
    for pl in placements:
        spend = pl.get('spend', 0)
        conversions = pl.get('conversions', 0)
        clicks = pl.get('clicks', 0)
        cpm = pl.get('cpm', 0)

        if spend > 5 and conversions == 0:
            wasted_segments.append({
                'segment': pl.get('placement_name', ''),
                'type': 'placement',
                'spend': spend,
                'clicks': clicks,
                'cpm': cpm,
                'issue': 'Zero conversions',
            })
        elif conversions > 0:
            cpa = spend / conversions
            top_segments.append({
                'segment': pl.get('placement_name', ''),
                'type': 'placement',
                'spend': spend,
                'conversions': conversions,
                'cpa': cpa,
            })

    # Sort by spend (most wasted first)
    wasted_segments.sort(key=lambda x: x['spend'], reverse=True)
    top_segments.sort(key=lambda x: x.get('cpa', 999999))

    total_wasted = sum(s['spend'] for s in wasted_segments)

    return {
        'wasted_segments': wasted_segments[:10],
        'top_segments': top_segments[:10],
        'total_wasted_spend': round(total_wasted, 2),
        'wasted_count': len(wasted_segments),
    }


def analyze_creative_fatigue(ads, campaigns):
    """
    Detect ads showing signs of creative fatigue.

    Key indicators:
    - Frequency > 3: Warning (CTR typically starts declining)
    - Frequency > 5: Critical (significant fatigue)
    - High impressions but declining CTR
    """
    fatigued_ads = []
    healthy_ads = []

    for ad in ads:
        frequency = ad.get('frequency', 0)
        ctr = ad.get('ctr', 0)
        impressions = ad.get('impressions', 0)
        spend = ad.get('spend', 0)

        if impressions < 100:
            continue  # Not enough data

        fatigue_level = 'healthy'
        issues = []

        if frequency > 5:
            fatigue_level = 'critical'
            issues.append(f'Frequency {frequency:.1f} (critical: ads shown too many times)')
        elif frequency > 3:
            fatigue_level = 'warning'
            issues.append(f'Frequency {frequency:.1f} (users seeing ad too often)')

        if ctr < 0.5 and impressions > 1000:
            if fatigue_level == 'healthy':
                fatigue_level = 'warning'
            issues.append(f'Low CTR ({ctr:.2f}%) despite {impressions:,} impressions')

        if fatigue_level != 'healthy':
            fatigued_ads.append({
                'ad_name': ad.get('ad_name', ''),
                'campaign_name': ad.get('campaign_name', ''),
                'frequency': frequency,
                'ctr': ctr,
                'impressions': impressions,
                'spend': spend,
                'fatigue_level': fatigue_level,
                'issues': issues,
                'headline': ad.get('headline', ''),
            })
        else:
            healthy_ads.append({
                'ad_name': ad.get('ad_name', ''),
                'frequency': frequency,
                'ctr': ctr,
                'conversions': ad.get('conversions', 0),
                'spend': spend,
            })

    # Also check campaign-level frequency
    campaign_fatigue = []
    for camp in campaigns:
        freq = camp.get('frequency', 0)
        if freq > 3:
            campaign_fatigue.append({
                'campaign_name': camp.get('campaign_name', ''),
                'frequency': freq,
                'reach': camp.get('reach', 0),
                'impressions': camp.get('impressions', 0),
                'severity': 'critical' if freq > 5 else 'warning',
            })

    fatigued_ads.sort(key=lambda x: x['frequency'], reverse=True)

    return {
        'fatigued_ads': fatigued_ads[:10],
        'healthy_ads': sorted(healthy_ads, key=lambda x: x.get('conversions', 0), reverse=True)[:5],
        'campaign_fatigue': campaign_fatigue,
        'total_fatigued': len(fatigued_ads),
    }


def analyze_placement_efficiency(placements):
    """
    Compare performance across placements.

    Identifies which placements (Feed, Stories, Reels, Audience Network)
    are performing well vs wasting money.
    """
    if not placements:
        return {'placements': [], 'best_placement': None, 'worst_placement': None}

    # Group by platform
    platform_summary = defaultdict(lambda: {
        'impressions': 0, 'clicks': 0, 'spend': 0, 'conversions': 0
    })

    for pl in placements:
        platform = pl.get('platform', 'unknown')
        platform_summary[platform]['impressions'] += pl.get('impressions', 0)
        platform_summary[platform]['clicks'] += pl.get('clicks', 0)
        platform_summary[platform]['spend'] += pl.get('spend', 0)
        platform_summary[platform]['conversions'] += pl.get('conversions', 0)

    platform_results = []
    for platform, data in platform_summary.items():
        spend = data['spend']
        conversions = data['conversions']
        clicks = data['clicks']
        impressions = data['impressions']

        platform_results.append({
            'platform': platform,
            'spend': round(spend, 2),
            'conversions': conversions,
            'cpa': round(spend / conversions, 2) if conversions > 0 else 0,
            'ctr': round(clicks / impressions * 100, 2) if impressions > 0 else 0,
            'cpm': round(spend / impressions * 1000, 2) if impressions > 0 else 0,
            'clicks': clicks,
        })

    platform_results.sort(key=lambda x: x['spend'], reverse=True)

    # Find best/worst by CPA (only if they have conversions)
    with_conversions = [p for p in platform_results if p['conversions'] > 0]
    best = min(with_conversions, key=lambda x: x['cpa']) if with_conversions else None
    worst = max(with_conversions, key=lambda x: x['cpa']) if len(with_conversions) > 1 else None

    # Individual placement analysis
    placement_details = []
    for pl in sorted(placements, key=lambda x: x['spend'], reverse=True):
        spend = pl.get('spend', 0)
        conversions = pl.get('conversions', 0)
        clicks = pl.get('clicks', 0)
        placement_details.append({
            'placement_name': pl.get('placement_name', ''),
            'platform': pl.get('platform', ''),
            'position': pl.get('position', ''),
            'spend': round(spend, 2),
            'clicks': clicks,
            'conversions': conversions,
            'cpa': round(spend / conversions, 2) if conversions > 0 else 0,
            'ctr': pl.get('ctr', 0),
            'cpm': pl.get('cpm', 0),
            'efficiency': 'good' if conversions > 0 and spend / conversions < 50 else (
                'poor' if spend > 10 and conversions == 0 else 'average'
            ),
        })

    return {
        'by_platform': platform_results,
        'placements': placement_details[:15],
        'best_platform': best,
        'worst_platform': worst,
    }


def analyze_budget_pacing(campaigns, days_in_range):
    """
    Analyze budget pacing and spending patterns.

    Same concept as Google Ads budget pacing but uses Facebook's
    daily_budget and lifetime_budget fields.
    """
    if not campaigns:
        return {}

    total_spend = sum(c['spend'] for c in campaigns)
    daily_avg = total_spend / days_in_range if days_in_range > 0 else 0
    projected_monthly = daily_avg * 30

    # Check individual campaign pacing
    pacing_details = []
    for camp in campaigns:
        daily_budget = camp.get('daily_budget', 0)
        lifetime_budget = camp.get('lifetime_budget', 0)
        camp_spend = camp.get('spend', 0)
        camp_daily_avg = camp_spend / days_in_range if days_in_range > 0 else 0

        if daily_budget > 0:
            utilization = (camp_daily_avg / daily_budget) * 100
            pacing_details.append({
                'campaign_name': camp.get('campaign_name', ''),
                'budget_type': 'daily',
                'budget': daily_budget,
                'avg_daily_spend': round(camp_daily_avg, 2),
                'utilization_pct': round(utilization, 1),
                'status': 'overspending' if utilization > 110 else (
                    'underspending' if utilization < 70 else 'on_track'
                ),
            })
        elif lifetime_budget > 0:
            utilization = (camp_spend / lifetime_budget) * 100
            pacing_details.append({
                'campaign_name': camp.get('campaign_name', ''),
                'budget_type': 'lifetime',
                'budget': lifetime_budget,
                'total_spend': round(camp_spend, 2),
                'utilization_pct': round(utilization, 1),
                'status': 'overspending' if utilization > 90 else (
                    'underspending' if utilization < 30 else 'on_track'
                ),
            })

    return {
        'total_spend': round(total_spend, 2),
        'daily_average': round(daily_avg, 2),
        'projected_monthly': round(projected_monthly, 2),
        'days_in_range': days_in_range,
        'campaign_pacing': pacing_details,
    }


def analyze_landing_page_performance(ads):
    """
    Analyze landing page performance from ad creative URLs.

    Same concept as Google Ads landing page heatmap.
    """
    if not ads:
        return {'heatmap': [], 'issues': []}

    # Group by landing page URL
    page_metrics = defaultdict(lambda: {
        'impressions': 0, 'clicks': 0, 'spend': 0,
        'conversions': 0, 'ad_count': 0, 'ad_names': []
    })

    for ad in ads:
        url = ad.get('link_url', '').strip()
        if not url:
            url = '(no URL)'

        # Normalize URL (remove tracking params)
        base_url = url.split('?')[0].rstrip('/')

        page_metrics[base_url]['impressions'] += ad.get('impressions', 0)
        page_metrics[base_url]['clicks'] += ad.get('clicks', 0)
        page_metrics[base_url]['spend'] += ad.get('spend', 0)
        page_metrics[base_url]['conversions'] += ad.get('conversions', 0)
        page_metrics[base_url]['ad_count'] += 1
        page_metrics[base_url]['ad_names'].append(ad.get('ad_name', ''))

    heatmap = []
    issues = []

    for url, data in page_metrics.items():
        clicks = data['clicks']
        conversions = data['conversions']
        spend = data['spend']

        conv_rate = (conversions / clicks * 100) if clicks > 0 else 0

        entry = {
            'url': url,
            'impressions': data['impressions'],
            'clicks': clicks,
            'spend': round(spend, 2),
            'conversions': conversions,
            'conversion_rate': round(conv_rate, 2),
            'ad_count': data['ad_count'],
            'color': 'green' if conv_rate >= 5 else ('orange' if conv_rate >= 2 else 'red'),
        }
        heatmap.append(entry)

        if clicks > 50 and conv_rate < 2:
            issues.append({
                'url': url,
                'issue': f'Low conversion rate ({conv_rate:.1f}%) with {clicks} clicks',
                'spend': round(spend, 2),
            })

    heatmap.sort(key=lambda x: x['clicks'], reverse=True)

    return {
        'heatmap': heatmap[:10],
        'issues': issues,
        'total_pages': len(page_metrics),
    }


def analyze_geo_performance(geo_data):
    """
    Analyze geographic performance.

    Same concept as Google Ads geo analysis.
    """
    if not geo_data:
        return {'locations': [], 'top_locations': [], 'poor_locations': []}

    # Sort by clicks
    sorted_geo = sorted(geo_data, key=lambda x: x.get('clicks', 0), reverse=True)

    top_locations = []
    poor_locations = []

    for geo in sorted_geo:
        spend = geo.get('spend', 0)
        conversions = geo.get('conversions', 0)
        clicks = geo.get('clicks', 0)

        if conversions > 0:
            cpa = spend / conversions
            top_locations.append({
                'location': geo.get('location_name', ''),
                'spend': round(spend, 2),
                'conversions': conversions,
                'cpa': round(cpa, 2),
                'clicks': clicks,
            })
        elif spend > 5 and clicks > 5:
            poor_locations.append({
                'location': geo.get('location_name', ''),
                'spend': round(spend, 2),
                'clicks': clicks,
                'issue': 'Zero conversions',
            })

    top_locations.sort(key=lambda x: x['cpa'])
    poor_locations.sort(key=lambda x: x['spend'], reverse=True)

    total_locations = len(sorted_geo)
    total_wasted = sum(p['spend'] for p in poor_locations)

    return {
        'locations': sorted_geo[:15],
        'top_locations': top_locations[:5],
        'poor_locations': poor_locations[:5],
        'total_locations': total_locations,
        'total_wasted_on_poor_locations': round(total_wasted, 2),
    }


def analyze_time_performance(time_data):
    """
    Analyze time-of-day and day-of-week performance.

    Same concept as Google Ads time analysis.
    """
    daily = time_data.get('daily', [])
    hourly = time_data.get('hourly', [])

    # Hourly analysis
    hourly_summary = defaultdict(lambda: {'clicks': 0, 'spend': 0, 'conversions': 0, 'impressions': 0})
    for h in hourly:
        hour = h.get('hour', 0)
        hourly_summary[hour]['clicks'] += h.get('clicks', 0)
        hourly_summary[hour]['spend'] += h.get('spend', 0)
        hourly_summary[hour]['conversions'] += h.get('conversions', 0)
        hourly_summary[hour]['impressions'] += h.get('impressions', 0)

    hourly_performance = []
    for hour in range(24):
        data = hourly_summary[hour]
        clicks = data['clicks']
        spend = data['spend']
        conversions = data['conversions']

        hourly_performance.append({
            'hour': hour,
            'hour_label': f'{hour:02d}:00',
            'clicks': clicks,
            'spend': round(spend, 2),
            'conversions': conversions,
            'cpa': round(spend / conversions, 2) if conversions > 0 else 0,
        })

    # Find best/worst hours
    best_hour = max(hourly_performance, key=lambda x: x['clicks']) if hourly_performance else None
    worst_hours = [h for h in hourly_performance if h['spend'] > 0 and h['conversions'] == 0]

    # Daily analysis - day of week
    dow_summary = defaultdict(lambda: {'clicks': 0, 'spend': 0, 'conversions': 0})
    for d in daily:
        date_str = d.get('date', '')
        if date_str:
            try:
                from datetime import datetime
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                dow = dt.strftime('%A')
                dow_summary[dow]['clicks'] += d.get('clicks', 0)
                dow_summary[dow]['spend'] += d.get('spend', 0)
                dow_summary[dow]['conversions'] += d.get('conversions', 0)
            except (ValueError, TypeError):
                pass

    daily_performance = []
    for dow in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
        data = dow_summary.get(dow, {'clicks': 0, 'spend': 0, 'conversions': 0})
        daily_performance.append({
            'day': dow,
            'clicks': data['clicks'],
            'spend': round(data['spend'], 2),
            'conversions': data['conversions'],
            'cpa': round(data['spend'] / data['conversions'], 2) if data['conversions'] > 0 else 0,
        })

    best_day = max(daily_performance, key=lambda x: x['clicks']) if daily_performance else None

    return {
        'hourly_performance': hourly_performance,
        'daily_performance': daily_performance,
        'best_hour': best_hour,
        'worst_hours': worst_hours[:5],
        'best_day': best_day,
        'worst_days': [d for d in daily_performance if d['spend'] > 0 and d['conversions'] == 0],
    }


def analyze_top_performers(campaigns, ad_sets):
    """
    Identify top-performing campaigns/ad sets that deserve budget scaling.

    Criteria: CPA below account average, conversion rate > 3%, active status.
    """
    # Calculate account-level averages
    total_spend = sum(c.get('spend', 0) for c in campaigns)
    total_conv = sum(c.get('conversions', 0) for c in campaigns)
    total_clicks = sum(c.get('clicks', 0) for c in campaigns)
    avg_cpa = total_spend / total_conv if total_conv > 0 else 0
    avg_conv_rate = (total_conv / total_clicks * 100) if total_clicks > 0 else 0

    scale_candidates = []
    review_candidates = []

    # Check campaigns
    for camp in campaigns:
        spend = camp.get('spend', 0)
        conversions = camp.get('conversions', 0)
        clicks = camp.get('clicks', 0)

        if spend < 10 or clicks < 10:
            continue

        cpa = spend / conversions if conversions > 0 else 0
        conv_rate = (conversions / clicks * 100) if clicks > 0 else 0

        if conversions > 0 and cpa < avg_cpa * 0.8 and conv_rate > 3:
            scale_candidates.append({
                'name': camp.get('campaign_name', ''),
                'level': 'campaign',
                'spend': round(spend, 2),
                'conversions': conversions,
                'cpa': round(cpa, 2),
                'conv_rate': round(conv_rate, 2),
                'vs_avg_cpa': round((1 - cpa / avg_cpa) * 100, 1) if avg_cpa > 0 else 0,
            })
        elif spend > 50 and conversions == 0:
            review_candidates.append({
                'name': camp.get('campaign_name', ''),
                'level': 'campaign',
                'spend': round(spend, 2),
                'clicks': clicks,
                'issue': 'High spend with zero conversions',
            })

    # Check ad sets
    for adset in ad_sets:
        spend = adset.get('spend', 0)
        conversions = adset.get('conversions', 0)
        clicks = adset.get('clicks', 0)

        if spend < 10 or clicks < 5:
            continue

        cpa = spend / conversions if conversions > 0 else 0
        conv_rate = (conversions / clicks * 100) if clicks > 0 else 0

        if conversions > 0 and cpa < avg_cpa * 0.7 and conv_rate > 3:
            scale_candidates.append({
                'name': adset.get('adset_name', ''),
                'level': 'ad_set',
                'campaign': adset.get('campaign_name', ''),
                'spend': round(spend, 2),
                'conversions': conversions,
                'cpa': round(cpa, 2),
                'conv_rate': round(conv_rate, 2),
                'vs_avg_cpa': round((1 - cpa / avg_cpa) * 100, 1) if avg_cpa > 0 else 0,
            })

    scale_candidates.sort(key=lambda x: x['cpa'])
    review_candidates.sort(key=lambda x: x['spend'], reverse=True)

    return {
        'scale_candidates': scale_candidates[:5],
        'review_candidates': review_candidates[:3],
        'account_avg_cpa': round(avg_cpa, 2),
        'account_avg_conv_rate': round(avg_conv_rate, 2),
    }


def analyze_audience_fatigue(campaigns, ads):
    """
    Detect audience saturation based on frequency metrics.

    High frequency (>4) indicates the same users are seeing ads too often,
    leading to ad blindness and wasted spend.
    """
    fatigued_campaigns = []
    fatigued_ads_list = []

    for camp in campaigns:
        freq = camp.get('frequency', 0)
        reach = camp.get('reach', 0)
        impressions = camp.get('impressions', 0)
        spend = camp.get('spend', 0)

        if freq > 4 and reach > 100:
            fatigued_campaigns.append({
                'campaign_name': camp.get('campaign_name', ''),
                'frequency': round(freq, 1),
                'reach': reach,
                'impressions': impressions,
                'spend': round(spend, 2),
                'severity': 'critical' if freq > 6 else 'warning',
                'suggestion': 'Create lookalike audience from converters' if freq > 6
                    else 'Expand age range or interest targeting',
            })

    for ad in ads:
        freq = ad.get('frequency', 0)
        impressions = ad.get('impressions', 0)

        if freq > 5 and impressions > 500:
            fatigued_ads_list.append({
                'ad_name': ad.get('ad_name', ''),
                'campaign_name': ad.get('campaign_name', ''),
                'frequency': round(freq, 1),
                'ctr': ad.get('ctr', 0),
                'spend': round(ad.get('spend', 0), 2),
            })

    fatigued_campaigns.sort(key=lambda x: x['frequency'], reverse=True)

    return {
        'fatigued_campaigns': fatigued_campaigns[:5],
        'fatigued_ads': fatigued_ads_list[:5],
        'total_fatigued_campaigns': len(fatigued_campaigns),
    }


def analyze_day_of_week_performance(time_data):
    """
    Analyze day-of-week patterns for bid adjustment recommendations.

    Flags days with spend but zero conversions, and identifies best-converting days.
    """
    daily_perf = time_data.get('daily_performance', [])
    if not daily_perf:
        return {'wasted_days': [], 'best_days': [], 'recommendations': []}

    wasted_days = []
    best_days = []

    for day in daily_perf:
        spend = day.get('spend', 0)
        conversions = day.get('conversions', 0)
        clicks = day.get('clicks', 0)

        if spend > 10 and conversions == 0:
            wasted_days.append({
                'day': day['day'],
                'spend': spend,
                'clicks': clicks,
                'issue': 'Zero conversions',
            })
        elif conversions > 0:
            cpa = spend / conversions
            best_days.append({
                'day': day['day'],
                'spend': spend,
                'conversions': conversions,
                'cpa': round(cpa, 2),
                'clicks': clicks,
            })

    best_days.sort(key=lambda x: x['cpa'])
    wasted_days.sort(key=lambda x: x['spend'], reverse=True)

    return {
        'wasted_days': wasted_days,
        'best_days': best_days[:3],
        'total_wasted_on_days': round(sum(d['spend'] for d in wasted_days), 2),
    }


def analyze_campaign_objective_alignment(campaigns):
    """
    Check if campaign objectives match actual performance.

    E.g., a campaign set to REACH but generating conversions should switch
    to a conversion-optimized objective.
    """
    mismatches = []

    conversion_objectives = {'OUTCOME_LEADS', 'OUTCOME_SALES', 'CONVERSIONS', 'LEAD_GENERATION'}
    awareness_objectives = {'REACH', 'BRAND_AWARENESS', 'OUTCOME_AWARENESS', 'POST_ENGAGEMENT',
                           'LINK_CLICKS', 'OUTCOME_ENGAGEMENT', 'OUTCOME_TRAFFIC'}

    for camp in campaigns:
        objective = camp.get('objective', '').upper()
        conversions = camp.get('conversions', 0)
        spend = camp.get('spend', 0)
        clicks = camp.get('clicks', 0)

        if not objective or spend < 10:
            continue

        # Awareness/traffic campaign generating conversions
        if objective in awareness_objectives and conversions > 2:
            cpa = spend / conversions if conversions > 0 else 0
            mismatches.append({
                'campaign_name': camp.get('campaign_name', ''),
                'current_objective': objective,
                'suggested_objective': 'CONVERSIONS / LEADS',
                'reason': f'Generating {conversions} conversions despite {objective} objective',
                'conversions': conversions,
                'cpa': round(cpa, 2),
                'spend': round(spend, 2),
                'priority': 'high',
            })

        # Conversion campaign with zero conversions
        elif objective in conversion_objectives and conversions == 0 and spend > 30:
            mismatches.append({
                'campaign_name': camp.get('campaign_name', ''),
                'current_objective': objective,
                'suggested_objective': 'Review targeting and creative',
                'reason': f'RM {spend:.2f} spent with 0 conversions despite conversion-optimized objective',
                'conversions': 0,
                'spend': round(spend, 2),
                'priority': 'high',
            })

    return {
        'mismatches': mismatches,
        'total_mismatches': len(mismatches),
    }


def analyze_roas_opportunities(campaigns, ad_sets):
    """
    Analyze ROAS (Return on Ad Spend) to find scaling and cut opportunities.

    Uses conversion_value and roas fields already fetched from the API.
    """
    scale_roas = []  # ROAS > 2.0 - worth scaling
    review_roas = []  # ROAS < 1.0 - losing money

    for camp in campaigns:
        roas = camp.get('roas', 0)
        conversion_value = camp.get('conversion_value', 0)
        spend = camp.get('spend', 0)

        if spend < 10:
            continue

        if roas > 2.0 and conversion_value > 0:
            scale_roas.append({
                'name': camp.get('campaign_name', ''),
                'level': 'campaign',
                'roas': round(roas, 2),
                'conversion_value': round(conversion_value, 2),
                'spend': round(spend, 2),
                'net_return': round(conversion_value - spend, 2),
            })
        elif 0 < roas < 1.0 and conversion_value > 0:
            review_roas.append({
                'name': camp.get('campaign_name', ''),
                'level': 'campaign',
                'roas': round(roas, 2),
                'conversion_value': round(conversion_value, 2),
                'spend': round(spend, 2),
                'loss': round(spend - conversion_value, 2),
            })

    # Also check ad sets
    for adset in ad_sets:
        roas = adset.get('roas', 0) if 'roas' in adset else (
            adset.get('conversion_value', 0) / adset.get('spend', 1) if adset.get('spend', 0) > 0 else 0
        )
        conversion_value = adset.get('conversion_value', 0)
        spend = adset.get('spend', 0)

        if spend < 10 or conversion_value == 0:
            continue

        if roas > 3.0:
            scale_roas.append({
                'name': adset.get('adset_name', ''),
                'level': 'ad_set',
                'campaign': adset.get('campaign_name', ''),
                'roas': round(roas, 2),
                'conversion_value': round(conversion_value, 2),
                'spend': round(spend, 2),
            })

    scale_roas.sort(key=lambda x: x['roas'], reverse=True)
    review_roas.sort(key=lambda x: x.get('loss', 0), reverse=True)

    return {
        'scale_opportunities': scale_roas[:5],
        'review_opportunities': review_roas[:3],
    }


def analyze_ad_creative_patterns(ads):
    """
    Compare ad creative performance to identify winning patterns.

    Analyzes headlines, CTAs, and landing pages to recommend A/B tests.
    """
    if not ads or len(ads) < 2:
        return {'patterns': [], 'test_suggestions': []}

    # Group performance by CTA type
    cta_performance = defaultdict(lambda: {'clicks': 0, 'conversions': 0, 'spend': 0, 'count': 0, 'impressions': 0})
    headline_performance = []

    for ad in ads:
        cta = ad.get('cta', 'unknown') or 'unknown'
        headline = ad.get('headline', '') or ''
        clicks = ad.get('clicks', 0)
        conversions = ad.get('conversions', 0)
        spend = ad.get('spend', 0)
        impressions = ad.get('impressions', 0)
        ctr = ad.get('ctr', 0)

        if impressions < 100:
            continue

        cta_performance[cta]['clicks'] += clicks
        cta_performance[cta]['conversions'] += conversions
        cta_performance[cta]['spend'] += spend
        cta_performance[cta]['count'] += 1
        cta_performance[cta]['impressions'] += impressions

        if headline:
            headline_performance.append({
                'headline': headline[:80],
                'ad_name': ad.get('ad_name', ''),
                'ctr': ctr,
                'conversions': conversions,
                'spend': round(spend, 2),
                'clicks': clicks,
            })

    # Analyze CTA performance
    cta_results = []
    for cta, data in cta_performance.items():
        conv_rate = (data['conversions'] / data['clicks'] * 100) if data['clicks'] > 0 else 0
        ctr = (data['clicks'] / data['impressions'] * 100) if data['impressions'] > 0 else 0
        cta_results.append({
            'cta': cta,
            'clicks': data['clicks'],
            'conversions': data['conversions'],
            'conv_rate': round(conv_rate, 2),
            'ctr': round(ctr, 2),
            'ad_count': data['count'],
            'spend': round(data['spend'], 2),
        })
    cta_results.sort(key=lambda x: x['conv_rate'], reverse=True)

    # Sort headlines by CTR for top/bottom performers
    headline_performance.sort(key=lambda x: x['ctr'], reverse=True)
    top_headlines = headline_performance[:3]
    bottom_headlines = headline_performance[-3:] if len(headline_performance) > 3 else []

    # Generate test suggestions
    test_suggestions = []
    if len(cta_results) > 1 and cta_results[0]['conv_rate'] > cta_results[-1]['conv_rate'] * 1.5:
        test_suggestions.append({
            'type': 'cta_test',
            'suggestion': f"Best CTA '{cta_results[0]['cta']}' outperforms '{cta_results[-1]['cta']}' "
                         f"({cta_results[0]['conv_rate']}% vs {cta_results[-1]['conv_rate']}% conversion rate). "
                         f"Test more ads with '{cta_results[0]['cta']}' CTA.",
        })

    if top_headlines and bottom_headlines:
        best_ctr = top_headlines[0]['ctr']
        worst_ctr = bottom_headlines[-1]['ctr']
        if best_ctr > 0 and worst_ctr >= 0 and best_ctr > worst_ctr * 2:
            test_suggestions.append({
                'type': 'headline_test',
                'suggestion': f"Top headline '{top_headlines[0]['headline'][:40]}...' has {best_ctr:.2f}% CTR "
                             f"vs bottom '{bottom_headlines[-1]['headline'][:40]}...' at {worst_ctr:.2f}%. "
                             f"Create variations of top-performing headline themes.",
            })

    return {
        'cta_performance': cta_results[:5],
        'top_headlines': top_headlines,
        'bottom_headlines': bottom_headlines,
        'test_suggestions': test_suggestions,
    }


def analyze_geo_bid_opportunities(geo_data):
    """
    Identify geographic locations for budget increase (not just exclusions).

    Finds top-converting locations where increasing spend would be profitable.
    """
    if not geo_data:
        return {'scale_locations': [], 'cut_locations': []}

    scale_locations = []
    cut_locations = []

    # Calculate average CPA across all geo locations
    total_spend = sum(g.get('spend', 0) for g in geo_data)
    total_conv = sum(g.get('conversions', 0) for g in geo_data)
    avg_cpa = total_spend / total_conv if total_conv > 0 else 0

    for geo in geo_data:
        spend = geo.get('spend', 0)
        conversions = geo.get('conversions', 0)
        clicks = geo.get('clicks', 0)
        location = geo.get('location_name', '')

        if spend < 5:
            continue

        if conversions > 0:
            cpa = spend / conversions
            if cpa < avg_cpa * 0.8:
                scale_locations.append({
                    'location': location,
                    'spend': round(spend, 2),
                    'conversions': conversions,
                    'cpa': round(cpa, 2),
                    'vs_avg': round((1 - cpa / avg_cpa) * 100, 1) if avg_cpa > 0 else 0,
                    'clicks': clicks,
                })
        elif spend > 10 and clicks > 5:
            cut_locations.append({
                'location': location,
                'spend': round(spend, 2),
                'clicks': clicks,
                'issue': 'Zero conversions',
            })

    scale_locations.sort(key=lambda x: x['cpa'])
    cut_locations.sort(key=lambda x: x['spend'], reverse=True)

    return {
        'scale_locations': scale_locations[:5],
        'cut_locations': cut_locations[:5],
        'avg_cpa': round(avg_cpa, 2),
    }
