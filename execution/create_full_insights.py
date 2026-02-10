#!/usr/bin/env python3
"""
Complete Google Ads insights workflow with Week 1 + Week 2 Quick Wins.
Generates comprehensive analysis including search queries, quality score roadmap, ROI, budget pacing, and landing page heatmap.
"""

import json
import sys
import os
sys.path.append('execution')

from analyze_advanced_insights import (
    analyze_search_queries,
    generate_quality_score_roadmap,
    calculate_roi_impact,
    generate_conversion_value_alert
)
from analyze_week2_insights import (
    analyze_budget_pacing,
    analyze_device_performance,
    analyze_landing_page_performance,
    analyze_geo_performance,
    analyze_time_performance
)
from impact_models import (
    calculate_exclusion_impact,
    calculate_bid_adjustment_impact,
    get_automation_metadata,
)

def create_enhanced_insights(metrics_file, output_insights, output_recommendations):
    """Generate enhanced insights with all Week 1 features."""

    print("Loading metrics...")
    with open(metrics_file, 'r') as f:
        metrics = json.load(f)

    summary = metrics.get('summary', {})
    campaigns = metrics.get('campaigns', [])
    keywords = metrics.get('keywords', [])
    search_queries = metrics.get('search_queries', [])

    print(f"Loaded: {len(campaigns)} campaigns, {len(keywords)} keywords, {len(search_queries)} search queries")

    # Run Week 1 analyses
    print("\nRunning search query analysis...")
    search_analysis = analyze_search_queries(search_queries, keywords)

    print("Generating quality score roadmap...")
    qs_roadmap = generate_quality_score_roadmap(keywords)

    print("Checking conversion value tracking...")
    conv_value_alert = generate_conversion_value_alert(summary)

    # Run Week 2 analyses
    print("Analyzing budget pacing...")
    budget_pacing = analyze_budget_pacing(metrics, monthly_budget=None)  # User can set budget later

    print("Analyzing device performance...")
    device_performance = analyze_device_performance(campaigns, keywords)

    print("Creating landing page heatmap...")
    ads = metrics.get('ads', [])
    landing_page_heatmap = analyze_landing_page_performance(keywords, ads)

    print("Analyzing geographic performance...")
    geo_data = metrics.get('geo_performance', [])
    # Get active campaign IDs for geo/schedule recommendations
    active_campaign_ids = [str(c['id']) for c in campaigns if c.get('status') == 'ENABLED']
    geo_performance = analyze_geo_performance(geo_data, active_campaign_ids)

    print("Analyzing time-of-day and day-of-week performance...")
    time_data = metrics.get('time_performance', [])
    time_performance = analyze_time_performance(time_data, active_campaign_ids)

    # Generate base insights (your existing logic)
    insights = {
        "summary": f"Analysis of Google Ads performance for customer {metrics.get('customer_id')} "
                   f"({metrics['date_range']['start_date']} to {metrics['date_range']['end_date']}). "
                   f"Generated {summary.get('total_conversions', 0):.1f} conversions at "
                   f"RM {summary.get('total_cost', 0) / max(summary.get('total_conversions', 1), 1):.2f} CPA "
                   f"from RM {summary.get('total_cost', 0):,.2f} spend.",

        "top_performers": [],
        "underperformers": [],
        "opportunities": [],
        "metrics_highlights": summary,

        # Week 1 Quick Wins
        "search_query_analysis": search_analysis,
        "quality_score_roadmap": qs_roadmap,
        "conversion_value_alert": conv_value_alert,

        # Week 2 Quick Wins
        "budget_pacing": budget_pacing,
        "device_performance": device_performance,
        "landing_page_heatmap": landing_page_heatmap,
        "geo_performance": geo_performance,

        # Week 3 Quick Wins
        "time_performance": time_performance
    }

    # Analyze top performers (require minimum spend for statistical significance)
    # Filter: at least 2 conversions OR min RM 10 spend to avoid single-click flukes
    performing_keywords = sorted(
        [k for k in keywords if k['conversions'] >= 2 or (k['conversions'] >= 1 and k['cost'] >= 10)],
        key=lambda x: x.get('cost_per_conversion', 999)
    )[:5]

    for kw in performing_keywords:
        insights["top_performers"].append(
            f"Keyword '{kw['keyword_text']}': {kw['conversions']:.0f} conversions at "
            f"RM {kw.get('cost_per_conversion', 0):.2f} CPA"
        )

    # Add search query insights to underperformers
    if search_analysis['total_wasted_spend'] > 0:
        insights["underperformers"].append(
            f"Search Query Waste: {len(search_analysis['wasted_spend_queries'])} queries with 0 conversions, "
            f"wasting RM {search_analysis['total_wasted_spend']:.2f}"
        )

    # Add quality score issues
    if qs_roadmap['total_low_qs'] > 0:
        insights["underperformers"].append(
            f"Quality Score Issues: {qs_roadmap['total_low_qs']} keywords with QS < 5, "
            f"spending RM {qs_roadmap['total_spend_low_qs']:.2f}"
        )

    # Generate recommendations
    recommendations = []

    # 1. KEYWORD PAUSE RECOMMENDATIONS - for low QS + no conversions
    low_qs_no_conv = [k for k in keywords if k.get('quality_score', 0) > 0 and
                      k['quality_score'] <= 2 and k['conversions'] == 0 and k['cost'] > 5]
    for kw in sorted(low_qs_no_conv, key=lambda x: x['cost'], reverse=True)[:3]:
        # Calculate impact
        impact_data = calculate_exclusion_impact(kw['cost'], conversions=0)
        automation = get_automation_metadata('keyword_action', platform='google')

        recommendations.append({
            "type": "keyword_action",
            "action": "pause",
            "target": kw.get('resource_name', kw['keyword_text']),
            "keyword": kw['keyword_text'],
            "current": "ENABLED",
            "suggested": "PAUSED",
            "reason": f"Quality Score of {kw['quality_score']}, 0 conversions, RM {kw['cost']:.2f} wasted. CTR {kw['ctr']*100:.1f}%",
            "expected_impact": f"Save RM {impact_data['monthly_savings']:.0f}/month ({impact_data['confidence_pct']}% confidence)",
            "impact_data": impact_data,
            "automation": automation,
        })

    # 2. BID INCREASE RECOMMENDATIONS - for top performers
    top_performers = [k for k in keywords if k['conversions'] >= 2 and k.get('cost_per_conversion', 999) < 15]
    for kw in sorted(top_performers, key=lambda x: x.get('cost_per_conversion', 999))[:3]:
        # Use actual avg CPC if keyword-level bid is 0 (ad group bidding)
        current_bid = kw.get('cpc_bid_micros', 0) / 1000000
        if current_bid == 0:
            current_bid = kw.get('avg_cpc', 0)
        suggested_bid = current_bid * 1.25  # 25% increase

        # Calculate impact
        impact_data = calculate_bid_adjustment_impact(
            current_bid=current_bid,
            suggested_bid=suggested_bid,
            keyword_spend=kw['cost'],
            keyword_conversions=kw['conversions']
        )
        automation = get_automation_metadata('bid_adjustment', platform='google')

        recommendations.append({
            "type": "bid_adjustment",
            "target": kw.get('resource_name', kw['keyword_text']),
            "keyword": kw['keyword_text'],
            "current_bid": current_bid,
            "suggested_bid": suggested_bid,
            "reason": f"Strong performer: {int(kw['conversions'])} conversions at RM {kw.get('cost_per_conversion', 0):.2f} CPA. CTR {kw['ctr']*100:.1f}%",
            "expected_impact": f"+{impact_data.get('additional_conversions_monthly', 0):.1f} conversions/month, +RM {impact_data.get('additional_revenue_monthly', 0):,.2f} revenue ({impact_data['confidence_pct']}% confidence)",
            "impact_data": impact_data,
            "automation": automation,
        })

    # 3. BID DECREASE RECOMMENDATIONS - for high spend, no conversions
    overpriced = [k for k in keywords if k['conversions'] == 0 and k['cost'] > 10 and k.get('quality_score', 0) >= 4]
    for kw in sorted(overpriced, key=lambda x: x['cost'], reverse=True)[:2]:
        # Use actual avg CPC if keyword-level bid is 0 (ad group bidding)
        current_bid = kw.get('cpc_bid_micros', 0) / 1000000
        if current_bid == 0:
            current_bid = kw.get('avg_cpc', 0)
        suggested_bid = current_bid * 0.65  # 35% decrease

        # Calculate impact
        impact_data = calculate_bid_adjustment_impact(
            current_bid=current_bid,
            suggested_bid=suggested_bid,
            keyword_spend=kw['cost'],
            keyword_conversions=kw['conversions']
        )
        automation = get_automation_metadata('bid_adjustment', platform='google')

        recommendations.append({
            "type": "bid_adjustment",
            "target": kw.get('resource_name', kw['keyword_text']),
            "keyword": kw['keyword_text'],
            "current_bid": current_bid,
            "suggested_bid": suggested_bid,
            "reason": f"0 conversions despite RM {kw['cost']:.2f} spend. Reduce bid to test at lower position",
            "expected_impact": f"Save RM {impact_data['monthly_savings']:.0f}/month ({impact_data['confidence_pct']}% confidence)",
            "impact_data": impact_data,
            "automation": automation,
        })

    # 4. AD COPY RECOMMENDATIONS - based on top performing ad groups
    ad_group_performance = {}
    for kw in keywords:
        ag_name = kw.get('ad_group_name', 'Unknown')
        if ag_name not in ad_group_performance:
            ad_group_performance[ag_name] = {'conversions': 0, 'clicks': 0, 'cost': 0, 'keywords': []}
        ad_group_performance[ag_name]['conversions'] += kw['conversions']
        ad_group_performance[ag_name]['clicks'] += kw['clicks']
        ad_group_performance[ag_name]['cost'] += kw['cost']
        ad_group_performance[ag_name]['keywords'].append(kw['keyword_text'])

    top_ad_groups = sorted(
        [(name, data) for name, data in ad_group_performance.items() if data['conversions'] > 5],
        key=lambda x: x[1]['conversions'],
        reverse=True
    )[:2]

    for ag_name, ag_data in top_ad_groups:
        # Find most common theme in keywords
        keywords_text = ' '.join(ag_data['keywords'][:5])

        # Generate image prompt based on ad group theme
        theme_lower = ag_name.lower()
        image_prompt = (
            f"Professional chiropractic care setting, showing a chiropractor treating a patient with {theme_lower}. "
            f"Modern, clean clinic environment with natural lighting. Patient appears relieved and comfortable. "
            f"Focus on professional healthcare atmosphere, trust, and wellness. "
            f"Photorealistic style, warm and inviting colors, high quality medical photography. "
            f"No text overlay needed."
        )

        automation = get_automation_metadata('ad_copy', platform='google')
        impact_data = {
            'monthly_savings': 0,
            'additional_conversions_monthly': ag_data['conversions'] * 0.12 * 4,  # 12% CTR improvement
            'confidence': 'moderate',
            'confidence_pct': 65,
            'formula': f"Estimated 12% CTR improvement from targeted ad copy",
            'assumptions': ['Better ad relevance', 'Improved Quality Score', 'Higher click-through rate']
        }

        recommendations.append({
            "type": "ad_copy",
            "ad_group_name": ag_name,
            "headline": f"{ag_name.title()} Relief | Book Today",
            "description": f"Expert chiropractic care for {ag_name.lower()}. Fast, effective relief.",
            "final_url": "https://www.yck.com.my",  # Default landing page - update based on campaign
            "image_prompt": image_prompt,
            "reason": f"Ad group '{ag_name}' has {int(ag_data['conversions'])} conversions. Create specific ad highlighting this theme",
            "expected_impact": f"Improve CTR by 10-15%, +{impact_data['additional_conversions_monthly']:.1f} conversions/month ({impact_data['confidence_pct']}% confidence)",
            "impact_data": impact_data,
            "automation": automation,
        })

    # 5. SEARCH QUERY-BASED NEGATIVE KEYWORDS
    seen_keywords = set()  # Dedup across sections 5 & 6
    for neg_kw in search_analysis.get('negative_keyword_suggestions', [])[:5]:
        kw_key = neg_kw['negative_keyword'].lower()
        if kw_key in seen_keywords:
            continue
        seen_keywords.add(kw_key)

        # Calculate impact
        impact_data = {
            'monthly_savings': neg_kw['wasted_spend'],
            'additional_conversions_monthly': 0,
            'confidence': 'high',
            'confidence_pct': 85,
            'formula': f"Prevents RM {neg_kw['wasted_spend']:.2f}/month in irrelevant clicks",
            'assumptions': ['Pattern will continue without negatives', 'No conversion potential from these queries']
        }
        automation = get_automation_metadata('keyword_action', platform='google')

        recommendations.append({
            "type": "keyword_action",
            "action": "add_negative",
            "target": f"Campaign-wide",
            "keyword": neg_kw['negative_keyword'],
            "current": "N/A",
            "suggested": f"NEGATIVE - {neg_kw['match_type']}",
            "reason": neg_kw['reason'],
            "expected_impact": f"Prevent RM {neg_kw['wasted_spend']:.2f} monthly waste ({impact_data['confidence_pct']}% confidence)",
            "impact_data": impact_data,
            "automation": automation,
        })

    # 6. SEARCH QUERY WASTE RECOMMENDATIONS
    for wasted in search_analysis.get('wasted_spend_queries', [])[:5]:
        if wasted['cost'] > 5:
            search_term = wasted['search_term'].lower()

            # Skip duplicates
            if search_term in seen_keywords:
                continue
            seen_keywords.add(search_term)

            # Detect specific negative keywords from the search term
            negative_keywords = []
            informational_words = ['exercises', 'symptoms', 'what is', 'how to', 'why', 'causes', 'pictures']
            product_words = ['shoes', 'brace', 'sleeve', 'support', 'insoles', 'cream', 'gel']
            diy_words = ['diy', 'home', 'natural', 'remedies', 'free', 'at home']

            for word in informational_words:
                if word in search_term:
                    negative_keywords.append(word)
            for word in product_words:
                if word in search_term:
                    negative_keywords.append(word)
            for word in diy_words:
                if word in search_term:
                    negative_keywords.append(word)

            # Generate specific action
            # Since these are wasted search queries (not actual keywords),
            # the best action is to add them as negative keywords
            if negative_keywords:
                # Add specific negative keywords if we detected problematic words
                action = "add_negative_keywords"
                suggested = f"Add negative keywords: {', '.join(negative_keywords[:3])}"
                target_negative_keywords = negative_keywords[:5]
            else:
                # Add the entire search query as a negative keyword
                action = "add_negative_keywords"
                suggested = f"Add '{wasted['search_term']}' as negative keyword (PHRASE match)"
                target_negative_keywords = [wasted['search_term']]

            # Calculate impact
            impact_data = calculate_exclusion_impact(wasted['cost'], conversions=0)
            automation = get_automation_metadata('keyword_action', platform='google')

            recommendations.append({
                "type": "keyword_action",
                "action": action,
                "target": wasted['ad_group'],  # Ad group name - for display purposes
                "campaign_id": str(wasted.get('campaign_id', '')),  # Campaign ID - for apply_recommendations.py
                "keyword": wasted['search_term'],
                "current": "Broad match triggering irrelevant searches",
                "suggested": suggested,
                "negative_keywords": target_negative_keywords,
                "reason": f"Zero conversions from '{wasted['search_term']}', wasted RM {wasted['cost']:.2f}",
                "expected_impact": f"Save RM {impact_data['monthly_savings']:.2f}/month ({impact_data['confidence_pct']}% confidence)",
                "how_to_apply": "Google Ads → Keywords → Select keyword → Add negative keywords",
                "impact_data": impact_data,
                "automation": automation,
            })

    # 7. QUALITY SCORE IMPROVEMENT RECOMMENDATIONS
    if qs_roadmap.get('improvement_plan'):
        for plan in qs_roadmap['improvement_plan'][:3]:
            automation = get_automation_metadata('quality_improvement', platform='google')
            impact_data = {
                'monthly_savings': 0,
                'additional_conversions_monthly': 0,
                'confidence': 'moderate',
                'confidence_pct': 60,
                'formula': plan['expected_impact'],
                'assumptions': ['Quality Score improvements require manual optimization', 'Results vary by implementation quality']
            }

            recommendations.append({
                "type": "quality_improvement",
                "action": "improve_quality_score",
                "target": f"{plan['affected_keywords']} keywords",
                "issue": plan['issue'],
                "current": f"QS < 5 affecting {plan['affected_keywords']} keywords",
                "suggested": plan['actions'][0] if plan['actions'] else "Review and optimize",
                "reason": f"Priority {plan['priority']}: {plan['issue']} affecting {plan['affected_keywords']} keywords",
                "expected_impact": f"{plan['expected_impact']} ({impact_data['confidence_pct']}% confidence)",
                "campaign_ids": active_campaign_ids,  # Add campaign IDs for automated application
                "impact_data": impact_data,
                "automation": automation,
            })

    # 8. GEOGRAPHIC RECOMMENDATIONS
    if geo_performance.get('recommendations'):
        for geo_rec in geo_performance['recommendations']:
            recommendations.append(geo_rec)

    # 9. TIME-OF-DAY / DAY-OF-WEEK RECOMMENDATIONS
    if time_performance.get('recommendations'):
        for time_rec in time_performance['recommendations']:
            recommendations.append(time_rec)

    # Calculate ROI
    print("Calculating ROI impact...")
    roi_analysis = calculate_roi_impact(recommendations, summary)

    # Add ROI to insights
    insights["roi_projection"] = roi_analysis

    # Save outputs
    print(f"\nSaving insights to {output_insights}...")
    with open(output_insights, 'w') as f:
        json.dump(insights, f, indent=2)

    print(f"Saving recommendations to {output_recommendations}...")
    with open(output_recommendations, 'w') as f:
        json.dump(recommendations, f, indent=2)

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print(f"\nKey Findings:")
    print(f"  - Search queries analyzed: {search_analysis['total_queries']}")
    print(f"  - Wasted spend identified: RM {search_analysis['total_wasted_spend']:.2f}")
    print(f"  - Low QS keywords: {qs_roadmap['total_low_qs']}")
    print(f"  - Negative keyword suggestions: {len(search_analysis.get('negative_keyword_suggestions', []))}")
    print(f"  - Total recommendations: {len(recommendations)}")
    print(f"\nExpected Monthly Impact:")
    print(f"  - Savings: RM {roi_analysis['monthly_savings']:.2f}")
    print(f"  - Additional revenue: RM {roi_analysis['estimated_monthly_revenue']:.2f}")
    print(f"  - Net benefit: RM {roi_analysis['net_monthly_benefit']:.2f}")

    if conv_value_alert:
        print(f"\n[WARNING] CRITICAL: {conv_value_alert['issue']}")

    return insights, recommendations


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python create_full_insights.py <metrics_file>")
        sys.exit(1)

    metrics_file = sys.argv[1]
    # Extract customer_id from filename like "google_ads_metrics_7867388610_20260128_215306.json"
    filename = os.path.basename(metrics_file)
    parts = filename.split('_')
    customer_id = parts[3] if len(parts) > 3 else 'unknown'

    output_insights = f".tmp/insights_enhanced_{customer_id}.json"
    output_recs = f".tmp/recommendations_enhanced_{customer_id}.json"

    create_enhanced_insights(metrics_file, output_insights, output_recs)
