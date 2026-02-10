#!/usr/bin/env python3
"""
Orchestrate Facebook/Meta Ads analysis and generate insights + recommendations.

Mirrors create_full_insights.py for Google Ads.

Usage:
    python execution/create_facebook_insights.py \
        --metrics_file .tmp/facebook_ads_metrics_XXXXX_20250131_120000.json

    # Or auto-detect latest metrics file:
    python execution/create_facebook_insights.py --ad_account_id XXXXX
"""

import json
import argparse
import glob
import os
from datetime import datetime

from analyze_facebook_insights import (
    analyze_audience_performance,
    analyze_creative_fatigue,
    analyze_placement_efficiency,
    analyze_budget_pacing,
    analyze_landing_page_performance,
    analyze_geo_performance,
    analyze_time_performance,
    analyze_top_performers,
    analyze_audience_fatigue,
    analyze_day_of_week_performance,
    analyze_campaign_objective_alignment,
    analyze_roas_opportunities,
    analyze_ad_creative_patterns,
    analyze_geo_bid_opportunities,
)

from impact_models import (
    calculate_exclusion_impact,
    calculate_scaling_impact,
    calculate_creative_refresh_impact,
    calculate_schedule_impact,
    get_automation_metadata,
)


def generate_insights_summary(metrics, audience_analysis, creative_analysis,
                               placement_analysis, budget_analysis):
    """Generate a high-level AI insights summary (narrative text)."""
    summary = metrics.get('summary', {})
    currency = metrics.get('currency', 'MYR')
    total_spend = summary.get('total_spend', 0)
    total_conversions = summary.get('total_conversions', 0)
    cpa = summary.get('overall_cpa', 0)
    ctr = summary.get('overall_ctr', 0)
    frequency = summary.get('total_frequency', 0)
    reach = summary.get('total_reach', 0)

    parts = []

    # Overall performance
    if total_conversions > 0:
        parts.append(
            f"Your Facebook Ads generated {total_conversions} conversions "
            f"from {currency} {total_spend:,.2f} spend, "
            f"with an average CPA of {currency} {cpa:,.2f}."
        )
    else:
        parts.append(
            f"Your Facebook Ads spent {currency} {total_spend:,.2f} "
            f"reaching {reach:,} people with {frequency:.1f}x average frequency, "
            f"but recorded 0 conversions. Check your conversion tracking setup."
        )

    # Wasted spend alert
    wasted = audience_analysis.get('total_wasted_spend', 0)
    if wasted > 0:
        parts.append(
            f"{currency} {wasted:,.2f} was spent on audience segments and placements "
            f"with zero conversions."
        )

    # Fatigue alert
    fatigued_count = creative_analysis.get('total_fatigued', 0)
    if fatigued_count > 0:
        parts.append(
            f"{fatigued_count} ad(s) are showing signs of creative fatigue "
            f"(high frequency). Consider refreshing these creatives."
        )

    # CTR insight
    if ctr < 1.0:
        parts.append(
            f"Overall CTR is {ctr:.2f}%, which is below average for Facebook Ads. "
            f"Review your ad creatives and targeting."
        )

    # Best placement
    best_platform = placement_analysis.get('best_platform')
    if best_platform:
        parts.append(
            f"Best performing platform: {best_platform['platform'].title()} "
            f"with CPA of {currency} {best_platform['cpa']:,.2f}."
        )

    return ' '.join(parts)


def generate_recommendations(metrics, audience_analysis, creative_analysis,
                              placement_analysis, budget_analysis, geo_analysis,
                              time_analysis, top_perf_analysis=None,
                              fatigue_analysis=None, dow_analysis=None,
                              objective_analysis=None, roas_analysis=None,
                              creative_pattern_analysis=None, geo_bid_analysis=None,
                              landing_page_analysis=None):
    """Generate actionable recommendations from all analyses."""
    recommendations = []
    currency = metrics.get('currency', 'MYR')

    # Find the top-performing ad set (by conversions) to apply exclusions to
    ad_sets = metrics.get('ad_sets', [])
    active_adsets = [a for a in ad_sets if a.get('conversions', 0) > 0 and a.get('status') == 'ACTIVE']

    # Default to the ad set with highest spend if no conversions
    if not active_adsets:
        active_adsets = [a for a in ad_sets if a.get('status') == 'ACTIVE']

    # Sort by conversions (or spend if no conversions)
    if active_adsets:
        top_adset = max(active_adsets, key=lambda x: (x.get('conversions', 0), x.get('spend', 0)))
        top_adset_id = top_adset.get('adset_id')
        top_adset_name = top_adset.get('adset_name')
    else:
        top_adset_id = None
        top_adset_name = None

    # 1. Audience exclusion recommendations
    for seg in audience_analysis.get('wasted_segments', [])[:3]:
        # Calculate impact
        impact_data = calculate_exclusion_impact(seg['spend'], conversions=0)
        automation = get_automation_metadata('audience_exclusion', platform='facebook')

        rec = {
            'type': 'audience_exclusion',
            'action': f"Exclude {seg['segment']}",
            'reason': f"Spent {currency} {seg['spend']:,.2f} with zero conversions on {seg['type']} segment '{seg['segment']}'.",
            'expected_impact': f"Save {currency} {impact_data['monthly_savings']:,.2f} monthly ({impact_data['confidence_pct']}% confidence)",
            'priority': 'high',
            'segment': seg['segment'],
            'segment_type': seg['type'],
            'adset_id': top_adset_id,  # Added for automation
            'adset_name': top_adset_name,  # Fallback for ID lookup
            'impact_data': impact_data,
            'automation': automation,
        }
        recommendations.append(rec)

    # 2. Creative fatigue recommendations
    for ad in creative_analysis.get('fatigued_ads', [])[:3]:
        severity = ad.get('fatigue_level', 'warning')

        # Calculate impact
        impact_data = calculate_creative_refresh_impact(
            spend=ad.get('spend', 0),
            frequency=ad.get('frequency', 1),
            current_ctr=ad.get('ctr', 0) / 100.0,  # Convert percentage to decimal
            current_conversions=ad.get('conversions', 0)
        )
        automation = get_automation_metadata('creative_refresh', platform='facebook')

        rec = {
            'type': 'creative_refresh',
            'action': f"Refresh ad: {ad['ad_name'][:50]}",
            'reason': f"Frequency {ad['frequency']:.1f}x, CTR {ad['ctr']:.2f}%. {'; '.join(ad.get('issues', []))}",
            'expected_impact': f"+{impact_data['ctr_improvement_pct']}% CTR, +{impact_data.get('additional_conversions_monthly', 0):.1f} conversions/month ({impact_data['confidence_pct']}% confidence)",
            'priority': 'high' if severity == 'critical' else 'medium',
            'ad_name': ad['ad_name'],
            'campaign_name': ad.get('campaign_name', ''),
            'impact_data': impact_data,
            'automation': automation,
        }
        recommendations.append(rec)

    # 3. Placement removal recommendations
    for pl in placement_analysis.get('placements', []):
        if pl.get('efficiency') == 'poor' and pl['spend'] > 10:
            # Calculate impact
            impact_data = calculate_exclusion_impact(pl['spend'], conversions=0)
            automation = get_automation_metadata('placement_exclusion', platform='facebook')

            rec = {
                'type': 'placement_exclusion',
                'action': f"Remove placement: {pl['placement_name']}",
                'reason': f"Spent {currency} {pl['spend']:,.2f} with zero conversions on {pl['placement_name']}.",
                'expected_impact': f"Save {currency} {impact_data['monthly_savings']:,.2f} monthly ({impact_data['confidence_pct']}% confidence)",
                'priority': 'high' if pl['spend'] > 50 else 'medium',
                'placement': pl['placement_name'],
                'adset_id': top_adset_id,  # Added for automation
                'adset_name': top_adset_name,  # Fallback for ID lookup
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)
            if len([r for r in recommendations if r['type'] == 'placement_exclusion']) >= 3:
                break

    # 4. Budget recommendations
    for pacing in budget_analysis.get('campaign_pacing', []):
        if pacing.get('status') == 'underspending':
            automation = get_automation_metadata('budget_adjustment', platform='facebook')
            impact_data = {
                'monthly_savings': 0,
                'additional_conversions_monthly': 0,
                'confidence': 'low',
                'confidence_pct': 50,
                'formula': 'Informational - results depend on campaign quality',
                'assumptions': ['Campaign is being limited by budget']
            }

            rec = {
                'type': 'budget_adjustment',
                'action': f"Increase budget for {pacing['campaign_name']}",
                'reason': f"Only using {pacing['utilization_pct']:.0f}% of {pacing['budget_type']} budget. Campaign may be limited.",
                'expected_impact': 'More impressions and potential conversions',
                'priority': 'medium',
                'campaign_name': pacing['campaign_name'],
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)
        elif pacing.get('status') == 'overspending':
            automation = get_automation_metadata('budget_adjustment', platform='facebook')
            impact_data = {
                'monthly_savings': 0,
                'additional_conversions_monthly': 0,
                'confidence': 'low',
                'confidence_pct': 50,
                'formula': 'Informational - review needed',
                'assumptions': ['Overspending may indicate good performance or budget misconfiguration']
            }

            rec = {
                'type': 'budget_adjustment',
                'action': f"Review overspend on {pacing['campaign_name']}",
                'reason': f"Spending {pacing['utilization_pct']:.0f}% of budget. Check campaign performance.",
                'expected_impact': 'Better budget control',
                'priority': 'low',
                'campaign_name': pacing['campaign_name'],
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)

    # 5. Geographic recommendations
    for loc in geo_analysis.get('poor_locations', [])[:2]:
        # Calculate impact
        impact_data = calculate_exclusion_impact(loc['spend'], conversions=0)
        automation = get_automation_metadata('geo_exclusion', platform='facebook')

        rec = {
            'type': 'geo_exclusion',
            'action': f"Exclude or reduce spend in {loc['location']}",
            'reason': f"Spent {currency} {loc['spend']:,.2f} with {loc['clicks']} clicks but zero conversions.",
            'expected_impact': f"Save {currency} {impact_data['monthly_savings']:,.2f} monthly ({impact_data['confidence_pct']}% confidence)",
            'priority': 'medium',
            'location': loc['location'],
            'adset_id': top_adset_id,  # Added for automation
            'adset_name': top_adset_name,  # Fallback for ID lookup
            'region_key': loc.get('region_key'),  # Location ID if available
            'impact_data': impact_data,
            'automation': automation,
        }
        recommendations.append(rec)

    # 6. Schedule recommendations
    best_hour = time_analysis.get('best_hour')
    worst_hours = time_analysis.get('worst_hours', [])
    best_hours_list = time_analysis.get('best_hours', [])
    if best_hour and worst_hours:
        wasted_in_worst = sum(h['spend'] for h in worst_hours)
        if wasted_in_worst > 10:
            # Extract hour values (not labels) for scheduling
            peak_hours = [h.get('hour', h.get('hour_label', '').split(':')[0]) for h in best_hours_list]
            # Convert to integers
            peak_hours = [int(h) if isinstance(h, (int, str)) and str(h).isdigit() else None for h in peak_hours]
            peak_hours = [h for h in peak_hours if h is not None]

            # Calculate impact
            impact_data = calculate_schedule_impact(wasted_hours_spend=wasted_in_worst)
            automation = get_automation_metadata('schedule_adjustment', platform='facebook')

            rec = {
                'type': 'schedule_adjustment',
                'action': f"Focus budget on peak hours (around {best_hour['hour_label']})",
                'reason': f"{currency} {wasted_in_worst:,.2f} spent during low-performing hours with zero conversions. Best hour: {best_hour['hour_label']} with {best_hour['clicks']} clicks.",
                'expected_impact': f"Save {currency} {impact_data['monthly_savings']:,.2f}/month + {impact_data['additional_conversions_monthly']:.1f} more conversions ({impact_data['confidence_pct']}% confidence)",
                'priority': 'medium',
                'adset_id': top_adset_id,  # Added for automation
                'adset_name': top_adset_name,  # Fallback for ID lookup
                'best_hours': peak_hours if peak_hours else [int(best_hour.get('hour', best_hour.get('hour_label', '').split(':')[0]))],
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)

    # 7. TOP PERFORMER SCALING
    if top_perf_analysis:
        for candidate in top_perf_analysis.get('scale_candidates', [])[:3]:
            # Calculate impact
            impact_data = calculate_scaling_impact(
                current_spend=candidate.get('spend', 0),
                current_conversions=candidate.get('conversions', 0),
                scale_factor=1.25
            )
            automation = get_automation_metadata('budget_scaling', platform='facebook')

            rec = {
                'type': 'budget_scaling',
                'action': f"Scale budget for {candidate['name']}",
                'reason': f"CPA {currency} {candidate['cpa']:,.2f} is {candidate['vs_avg_cpa']}% below account average. "
                         f"Conversion rate {candidate['conv_rate']}% with {candidate['conversions']} conversions.",
                'expected_impact': f"+{impact_data['additional_conversions_monthly']:.1f} conversions/month, +{currency} {impact_data.get('additional_revenue_monthly', 0):,.2f} revenue ({impact_data['confidence_pct']}% confidence)",
                'priority': 'high',
                'campaign_name': candidate['name'],
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)

        for candidate in top_perf_analysis.get('review_candidates', [])[:2]:
            # Calculate impact (savings from pausing)
            impact_data = calculate_exclusion_impact(candidate.get('spend', 0), conversions=0)
            automation = get_automation_metadata('campaign_review', platform='facebook')

            rec = {
                'type': 'campaign_review',
                'action': f"Review or pause {candidate['name']}",
                'reason': f"Spent {currency} {candidate['spend']:,.2f} with zero conversions. {candidate['clicks']} clicks but no results.",
                'expected_impact': f"Save {currency} {impact_data['monthly_savings']:,.2f} monthly or fix conversion tracking ({impact_data['confidence_pct']}% confidence)",
                'priority': 'high',
                'campaign_name': candidate['name'],
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)

    # 8. AUDIENCE FATIGUE
    if fatigue_analysis:
        for camp in fatigue_analysis.get('fatigued_campaigns', [])[:2]:
            automation = get_automation_metadata('audience_fatigue', platform='facebook')
            impact_data = {
                'monthly_savings': 0,
                'additional_conversions_monthly': camp.get('conversions', 0) * 0.15 * 4,  # Estimate 15% improvement
                'confidence': 'moderate',
                'confidence_pct': 65,
                'formula': f"Frequency reduction from {camp['frequency']:.1f}x → estimated 15% conversion improvement",
                'assumptions': ['Expanding audience reduces frequency', 'Fresh users convert better']
            }

            rec = {
                'type': 'audience_fatigue',
                'action': f"Expand audience for {camp['campaign_name']}",
                'reason': f"Frequency {camp['frequency']}x - audience is seeing ads too often "
                         f"(reach: {camp['reach']:,}). {camp['suggestion']}.",
                'expected_impact': f"Reduce frequency, +{impact_data['additional_conversions_monthly']:.1f} conversions/month ({impact_data['confidence_pct']}% confidence)",
                'priority': 'high' if camp['severity'] == 'critical' else 'medium',
                'campaign_name': camp['campaign_name'],
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)

    # 9. DAY-OF-WEEK OPTIMIZATION
    if dow_analysis:
        wasted_days = dow_analysis.get('wasted_days', [])
        best_days = dow_analysis.get('best_days', [])
        if wasted_days:
            day_names = ', '.join(d['day'] for d in wasted_days[:3])
            total_wasted = dow_analysis.get('total_wasted_on_days', 0)

            # Calculate impact
            impact_data = calculate_schedule_impact(wasted_hours_spend=total_wasted)
            automation = get_automation_metadata('day_schedule', platform='facebook')

            rec = {
                'type': 'day_schedule',
                'action': f"Reduce spend on {day_names}",
                'reason': f"{currency} {total_wasted:,.2f} spent on zero-conversion days ({day_names}).",
                'expected_impact': f"Save {currency} {impact_data['monthly_savings']:,.2f}/month + {impact_data['additional_conversions_monthly']:.1f} more conversions ({impact_data['confidence_pct']}% confidence)",
                'priority': 'medium',
                'impact_data': impact_data,
                'automation': automation,
                'wasted_days': [d['day'] for d in wasted_days[:3]],
            }
            if best_days:
                rec['reason'] += f" Best day: {best_days[0]['day']} ({best_days[0]['conversions']} conversions, CPA {currency} {best_days[0]['cpa']:,.2f})."
            recommendations.append(rec)

    # 10. CAMPAIGN OBJECTIVE MISMATCH
    if objective_analysis:
        for mismatch in objective_analysis.get('mismatches', [])[:2]:
            automation = get_automation_metadata('objective_mismatch', platform='facebook')
            impact_data = {
                'monthly_savings': 0,
                'additional_conversions_monthly': mismatch.get('conversions', 0) * 0.20 * 4,  # Estimate 20% improvement
                'confidence': 'moderate',
                'confidence_pct': 65,
                'formula': 'Estimated 20% CPA improvement from proper objective alignment',
                'assumptions': ['Better algorithm optimization', 'Improved audience targeting']
            }

            rec = {
                'type': 'objective_mismatch',
                'action': f"Switch {mismatch['campaign_name']} to {mismatch['suggested_objective']}",
                'reason': mismatch['reason'],
                'expected_impact': f"Better optimization, ~20% lower CPA ({impact_data['confidence_pct']}% confidence)",
                'priority': mismatch.get('priority', 'medium'),
                'campaign_name': mismatch['campaign_name'],
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)

    # 11. ROAS OPTIMIZATION
    if roas_analysis:
        for opp in roas_analysis.get('scale_opportunities', [])[:2]:
            # Calculate impact - for high ROAS, scaling is beneficial
            conversions = opp.get('conversion_value', 0) / 200  # Estimate conversions
            impact_data = calculate_scaling_impact(
                current_spend=opp.get('spend', 0),
                current_conversions=conversions,
                scale_factor=1.30,
                customer_value=200
            )
            automation = get_automation_metadata('roas_scaling', platform='facebook')

            rec = {
                'type': 'roas_scaling',
                'action': f"Scale {opp['name']} (ROAS {opp['roas']}x)",
                'reason': f"Generating {currency} {opp['conversion_value']:,.2f} from {currency} {opp['spend']:,.2f} spend. "
                         f"ROAS {opp['roas']}x is highly profitable.",
                'expected_impact': f"+{currency} {impact_data.get('additional_revenue_monthly', 0):,.2f} revenue/month ({impact_data['confidence_pct']}% confidence)",
                'priority': 'high',
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)

        for opp in roas_analysis.get('review_opportunities', [])[:2]:
            # For negative ROAS, savings come from reducing/pausing
            loss_monthly = opp.get('loss', 0) * 4
            automation = get_automation_metadata('roas_review', platform='facebook')
            impact_data = {
                'monthly_savings': loss_monthly,
                'additional_conversions_monthly': 0,
                'confidence': 'high',
                'confidence_pct': 85,
                'formula': f"Weekly loss (RM {opp.get('loss', 0):.2f}) × 4 weeks = RM {loss_monthly:.2f} saved",
                'assumptions': ['Negative ROAS indicates losing money', 'Reducing budget stops the loss']
            }

            rec = {
                'type': 'roas_review',
                'action': f"Review {opp['name']} (ROAS {opp['roas']}x - losing money)",
                'reason': f"Spending {currency} {opp['spend']:,.2f} but only {currency} {opp['conversion_value']:,.2f} return. "
                         f"Losing {currency} {opp.get('loss', 0):,.2f}.",
                'expected_impact': f"Stop losing {currency} {loss_monthly:,.2f}/month ({impact_data['confidence_pct']}% confidence)",
                'priority': 'high',
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)

    # 12. CREATIVE TESTING
    if creative_pattern_analysis:
        for suggestion in creative_pattern_analysis.get('test_suggestions', [])[:2]:
            automation = get_automation_metadata('creative_test', platform='facebook')
            impact_data = {
                'monthly_savings': 0,
                'additional_conversions_monthly': 0,
                'confidence': 'moderate',
                'confidence_pct': 60,
                'formula': 'A/B testing can yield 10-30% CTR improvements',
                'assumptions': ['Requires creative development', 'Results vary by test quality']
            }

            rec = {
                'type': 'creative_test',
                'action': f"A/B Test: {suggestion['type'].replace('_', ' ').title()}",
                'reason': suggestion['suggestion'],
                'expected_impact': 'Improve CTR and conversion rate through systematic testing (10-30% potential uplift)',
                'priority': 'medium',
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)

    # 13. GEO BID ADJUSTMENTS (scale, not just exclude)
    if geo_bid_analysis:
        for loc in geo_bid_analysis.get('scale_locations', [])[:2]:
            # Calculate impact - scaling good geos
            impact_data = calculate_scaling_impact(
                current_spend=loc.get('spend', 0),
                current_conversions=loc.get('conversions', 0),
                scale_factor=1.20
            )
            automation = get_automation_metadata('geo_scaling', platform='facebook')

            rec = {
                'type': 'geo_scaling',
                'action': f"Increase spend in {loc['location']}",
                'reason': f"CPA {currency} {loc['cpa']:,.2f} is {loc['vs_avg']}% below average. "
                         f"{loc['conversions']} conversions from {currency} {loc['spend']:,.2f} spend.",
                'expected_impact': f"+{impact_data['additional_conversions_monthly']:.1f} conversions/month at {currency} {loc['cpa']:,.2f} CPA ({impact_data['confidence_pct']}% confidence)",
                'priority': 'medium',
                'location': loc['location'],
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)

    # 14. LANDING PAGE ISSUES
    if landing_page_analysis:
        for issue in landing_page_analysis.get('issues', [])[:2]:
            automation = get_automation_metadata('landing_page', platform='facebook')
            # Estimate impact - landing page improvements can yield 20-50% conversion uplift
            current_conversions = issue.get('conversions', 0)
            estimated_uplift = current_conversions * 0.30  # Conservative 30% estimate
            impact_data = {
                'monthly_savings': 0,
                'additional_conversions_monthly': estimated_uplift * 4,
                'confidence': 'moderate',
                'confidence_pct': 65,
                'formula': f"Estimated 30% conversion rate improvement from landing page optimization",
                'assumptions': ['Landing page speed/UX improvements', 'Better conversion funnel', 'Requires website changes']
            }

            rec = {
                'type': 'landing_page',
                'action': f"Optimize landing page: {issue['url'][:60]}",
                'reason': f"{issue['issue']}. {currency} {issue['spend']:,.2f} spent driving traffic to underperforming page.",
                'expected_impact': f"Improve conversion rate +30%, ~{estimated_uplift * 4:.1f} more conversions/month ({impact_data['confidence_pct']}% confidence)",
                'priority': 'medium',
                'impact_data': impact_data,
                'automation': automation,
            }
            recommendations.append(rec)

    # Sort by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    recommendations.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 2))

    return recommendations[:20]


def main():
    parser = argparse.ArgumentParser(description="Generate Facebook Ads insights and recommendations")
    parser.add_argument('--metrics_file', help='Path to Facebook metrics JSON')
    parser.add_argument('--ad_account_id', help='Auto-detect latest metrics for this account')
    parser.add_argument('--output_dir', default='.tmp', help='Output directory')

    args = parser.parse_args()

    # Find metrics file
    metrics_file = args.metrics_file
    if not metrics_file and args.ad_account_id:
        clean_id = args.ad_account_id.replace('act_', '')
        pattern = f'.tmp/facebook_ads_metrics_{clean_id}_*.json'
        files = glob.glob(pattern)
        if files:
            metrics_file = max(files)
            print(f"Using latest metrics: {metrics_file}")
        else:
            print(f"[ERROR] No metrics file found matching: {pattern}")
            return
    elif not metrics_file:
        # Try to find any Facebook metrics file
        files = glob.glob('.tmp/facebook_ads_metrics_*.json')
        if files:
            metrics_file = max(files)
            print(f"Using latest metrics: {metrics_file}")
        else:
            print("[ERROR] No metrics file specified or found. Run fetch_facebook_ads_metrics.py first.")
            return

    # Load metrics
    with open(metrics_file, 'r') as f:
        metrics = json.load(f)

    ad_account_id = metrics.get('ad_account_id', 'unknown')
    clean_id = ad_account_id.replace('act_', '')
    currency = metrics.get('currency', 'MYR')

    print(f"\n{'='*70}")
    print(f"FACEBOOK ADS INSIGHTS ANALYSIS")
    print(f"{'='*70}")
    print(f"  Account: {metrics.get('account_name', 'Unknown')} ({ad_account_id})")
    print(f"  Date Range: {metrics['date_range']['start_date']} to {metrics['date_range']['end_date']}")
    print(f"  Currency: {currency}")
    print(f"{'='*70}\n")

    # Calculate days in range
    from datetime import datetime
    start = datetime.strptime(metrics['date_range']['start_date'], '%Y-%m-%d')
    end = datetime.strptime(metrics['date_range']['end_date'], '%Y-%m-%d')
    days_in_range = (end - start).days or 1

    # Run all analyses
    print("Running analyses...")

    audience_analysis = analyze_audience_performance(
        metrics.get('demographic_breakdown', []),
        metrics.get('placement_breakdown', [])
    )
    print(f"  Audience: {audience_analysis['wasted_count']} wasted segments found")

    creative_analysis = analyze_creative_fatigue(
        metrics.get('ads', []),
        metrics.get('campaigns', [])
    )
    print(f"  Creative: {creative_analysis['total_fatigued']} fatigued ads")

    placement_analysis = analyze_placement_efficiency(
        metrics.get('placement_breakdown', [])
    )
    print(f"  Placements: {len(placement_analysis.get('placements', []))} analyzed")

    budget_analysis = analyze_budget_pacing(
        metrics.get('campaigns', []),
        days_in_range
    )
    print(f"  Budget: {len(budget_analysis.get('campaign_pacing', []))} campaigns tracked")

    landing_page_analysis = analyze_landing_page_performance(
        metrics.get('ads', [])
    )
    print(f"  Landing Pages: {landing_page_analysis.get('total_pages', 0)} pages analyzed")

    geo_analysis = analyze_geo_performance(
        metrics.get('geo_performance', [])
    )
    print(f"  Geo: {geo_analysis.get('total_locations', 0)} locations")

    time_analysis = analyze_time_performance(
        metrics.get('time_performance', {})
    )
    print(f"  Time: {len(time_analysis.get('hourly_performance', []))} hours analyzed")

    # New analyses
    top_perf_analysis = analyze_top_performers(
        metrics.get('campaigns', []),
        metrics.get('ad_sets', [])
    )
    print(f"  Top Performers: {len(top_perf_analysis.get('scale_candidates', []))} scale candidates")

    fatigue_analysis = analyze_audience_fatigue(
        metrics.get('campaigns', []),
        metrics.get('ads', [])
    )
    print(f"  Audience Fatigue: {fatigue_analysis.get('total_fatigued_campaigns', 0)} fatigued campaigns")

    dow_analysis = analyze_day_of_week_performance(time_analysis)
    print(f"  Day-of-Week: {len(dow_analysis.get('wasted_days', []))} wasted days")

    objective_analysis = analyze_campaign_objective_alignment(
        metrics.get('campaigns', [])
    )
    print(f"  Objective Alignment: {objective_analysis.get('total_mismatches', 0)} mismatches")

    roas_analysis = analyze_roas_opportunities(
        metrics.get('campaigns', []),
        metrics.get('ad_sets', [])
    )
    print(f"  ROAS: {len(roas_analysis.get('scale_opportunities', []))} scale, {len(roas_analysis.get('review_opportunities', []))} review")

    creative_pattern_analysis = analyze_ad_creative_patterns(
        metrics.get('ads', [])
    )
    print(f"  Creative Patterns: {len(creative_pattern_analysis.get('test_suggestions', []))} test suggestions")

    geo_bid_analysis = analyze_geo_bid_opportunities(
        metrics.get('geo_performance', [])
    )
    print(f"  Geo Bids: {len(geo_bid_analysis.get('scale_locations', []))} scale locations")

    # Generate summary
    summary_text = generate_insights_summary(
        metrics, audience_analysis, creative_analysis,
        placement_analysis, budget_analysis
    )

    # Generate recommendations
    recommendations = generate_recommendations(
        metrics, audience_analysis, creative_analysis,
        placement_analysis, budget_analysis, geo_analysis,
        time_analysis,
        top_perf_analysis=top_perf_analysis,
        fatigue_analysis=fatigue_analysis,
        dow_analysis=dow_analysis,
        objective_analysis=objective_analysis,
        roas_analysis=roas_analysis,
        creative_pattern_analysis=creative_pattern_analysis,
        geo_bid_analysis=geo_bid_analysis,
        landing_page_analysis=landing_page_analysis,
    )

    # Build insights output
    insights = {
        'ad_account_id': ad_account_id,
        'account_name': metrics.get('account_name', ''),
        'generated_at': datetime.now().isoformat(),
        'date_range': metrics['date_range'],
        'summary': summary_text,
        'audience_performance': audience_analysis,
        'creative_fatigue': creative_analysis,
        'placement_efficiency': placement_analysis,
        'budget_pacing': budget_analysis,
        'landing_page_performance': landing_page_analysis,
        'geo_performance': geo_analysis,
        'time_performance': time_analysis,
        'top_performers': top_perf_analysis,
        'audience_fatigue': fatigue_analysis,
        'day_of_week': dow_analysis,
        'objective_alignment': objective_analysis,
        'roas_opportunities': roas_analysis,
        'creative_patterns': creative_pattern_analysis,
        'geo_bid_opportunities': geo_bid_analysis,
    }

    # Save insights
    os.makedirs(args.output_dir, exist_ok=True)
    insights_file = os.path.join(args.output_dir, f'facebook_insights_{clean_id}.json')
    with open(insights_file, 'w') as f:
        json.dump(insights, f, indent=2, default=str)

    # Save recommendations
    recs_file = os.path.join(args.output_dir, f'facebook_recommendations_{clean_id}.json')
    with open(recs_file, 'w') as f:
        json.dump(recommendations, f, indent=2, default=str)

    print(f"\n{'='*70}")
    print(f"ANALYSIS COMPLETE")
    print(f"{'='*70}")
    print(f"  Insights: {insights_file}")
    print(f"  Recommendations: {recs_file} ({len(recommendations)} items)")
    print(f"\n  Summary:")
    print(f"  {summary_text}")
    print(f"\n  Top recommendations:")
    for i, rec in enumerate(recommendations[:5], 1):
        print(f"    {i}. [{rec['priority'].upper()}] {rec['action']}")
    print(f"{'='*70}\n")

    return insights_file, recs_file


if __name__ == '__main__':
    main()
