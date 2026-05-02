#!/usr/bin/env python3
"""
Advanced analysis functions for Google Ads insights.
Includes search query analysis, quality score roadmap, and ROI calculations.
"""

import json
import os
from collections import defaultdict


def analyze_search_queries(search_queries, keywords):
    """
    Analyze search queries to find wasted spend and suggest negative keywords.

    Returns insights about:
    - High-cost, zero-conversion search terms
    - Irrelevant search patterns
    - Recommended negative keywords
    """
    if not search_queries:
        return {
            "total_queries": 0,
            "wasted_spend_queries": [],
            "negative_keyword_suggestions": [],
            "insights": ["Search query data not available for this account"]
        }

    wasted_queries = []
    total_wasted_spend = 0

    # Identify problematic search terms
    for query in search_queries:
        # Zero conversions with significant spend
        if query['conversions'] == 0 and query['cost'] > 5:
            wasted_queries.append({
                "search_term": query['search_term'],
                "cost": query['cost'],
                "clicks": query['clicks'],
                "impressions": query['impressions'],
                "campaign_name": query['campaign_name'],
                "campaign_id": query.get('campaign_id', ''),  # Include campaign ID for apply_recommendations.py
                "ad_group_name": query['ad_group_name']
            })
            total_wasted_spend += query['cost']

    # Sort by cost (highest waste first)
    wasted_queries.sort(key=lambda x: x['cost'], reverse=True)

    # Generate negative keyword suggestions
    negative_suggestions = []
    seen_terms = set()

    for query in wasted_queries[:20]:  # Top 20 wasted queries
        search_term = query['search_term'].lower()

        # Look for common problematic patterns
        problematic_words = [
            'free', 'cheap', 'diy', 'how to', 'what is', 'why',
            'meme', 'joke', 'funny', 'video', 'youtube',
            'jobs', 'salary', 'course', 'training', 'school'
        ]

        for word in problematic_words:
            if word in search_term and word not in seen_terms:
                negative_suggestions.append({
                    "negative_keyword": word,
                    "match_type": "PHRASE",
                    "reason": f"Found in zero-conversion query: '{query['search_term']}'",
                    "wasted_spend": query['cost'],
                    "example_query": query['search_term']
                })
                seen_terms.add(word)

    insights = []
    if len(wasted_queries) > 0:
        insights.append(f"Found {len(wasted_queries)} search queries with 0 conversions, wasting RM {total_wasted_spend:.2f}")
    if len(negative_suggestions) > 0:
        insights.append(f"Identified {len(negative_suggestions)} negative keyword opportunities")

    return {
        "total_queries": len(search_queries),
        "wasted_spend_queries": wasted_queries[:10],  # Top 10
        "total_wasted_spend": total_wasted_spend,
        "negative_keyword_suggestions": negative_suggestions,
        "insights": insights
    }


def generate_quality_score_roadmap(keywords):
    """
    Generate a structured improvement plan for low quality scores.
    """
    low_qs_keywords = [k for k in keywords if k.get('quality_score', 0) > 0 and k['quality_score'] < 5]

    if not low_qs_keywords:
        return {
            "total_low_qs": 0,
            "improvement_plan": [],
            "expected_impact": ""
        }

    # Group by issue type
    issues = defaultdict(list)

    for kw in low_qs_keywords:
        ad_rel = kw.get('ad_relevance', 'UNSPECIFIED')
        lp_exp = kw.get('landing_page_experience', 'UNSPECIFIED')
        exp_ctr = kw.get('expected_ctr', 'UNSPECIFIED')

        if 'BELOW' in ad_rel:
            issues['ad_relevance'].append(kw)
        if 'BELOW' in lp_exp:
            issues['landing_page'].append(kw)
        if 'BELOW' in exp_ctr:
            issues['expected_ctr'].append(kw)

    improvement_plan = []

    # Landing Page Improvements
    if issues['landing_page']:
        improvement_plan.append({
            "issue": "Landing Page Experience",
            "affected_keywords": len(issues['landing_page']),
            "priority": "HIGH",
            "actions": [
                "Create dedicated landing pages for each ad group theme",
                "Improve page load speed (target < 3 seconds)",
                "Add trust signals (testimonials, certifications, reviews)",
                "Ensure mobile-friendliness",
                "Match page content to keyword intent"
            ],
            "expected_impact": "QS +2-3 points, CPC reduction 20-30%",
            "estimated_time": "2-3 weeks"
        })

    # Ad Relevance Improvements
    if issues['ad_relevance']:
        improvement_plan.append({
            "issue": "Ad Relevance",
            "affected_keywords": len(issues['ad_relevance']),
            "priority": "MEDIUM",
            "actions": [
                "Create ad group-specific ad copy",
                "Include primary keyword in headline",
                "Match ad copy to landing page content",
                "Use Dynamic Keyword Insertion (DKI) where appropriate",
                "Test 3-4 ad variations per ad group"
            ],
            "expected_impact": "QS +1-2 points, CTR +10-15%",
            "estimated_time": "1 week"
        })

    # Expected CTR Improvements
    if issues['expected_ctr']:
        improvement_plan.append({
            "issue": "Expected CTR",
            "affected_keywords": len(issues['expected_ctr']),
            "priority": "MEDIUM",
            "actions": [
                "Add all available ad extensions (sitelinks, callouts, structured snippets)",
                "Test promotional offers in headlines",
                "Use call-to-action phrases (Book Now, Get Quote, Call Today)",
                "Add price extensions if applicable",
                "Test ad scheduling (show ads during peak hours)"
            ],
            "expected_impact": "CTR +5-10%, QS +1 point",
            "estimated_time": "3-5 days"
        })

    # Calculate total potential savings
    total_cost = sum(k['cost'] for k in low_qs_keywords)
    avg_qs_improvement = 2  # Conservative estimate
    cpc_reduction = 0.25  # 25% CPC reduction with +2 QS
    monthly_savings = (total_cost / 7) * 30 * cpc_reduction  # Extrapolate to monthly

    return {
        "total_low_qs": len(low_qs_keywords),
        "avg_quality_score": sum(k['quality_score'] for k in low_qs_keywords) / len(low_qs_keywords),
        "total_spend_low_qs": total_cost,
        "improvement_plan": improvement_plan,
        "expected_impact": f"Estimated monthly savings: RM {monthly_savings:.2f} with QS improvements",
        "affected_keywords_sample": [
            {
                "keyword": k['keyword_text'],
                "qs": k['quality_score'],
                "ad_rel": k.get('ad_relevance', 'N/A'),
                "lp_exp": k.get('landing_page_experience', 'N/A'),
                "exp_ctr": k.get('expected_ctr', 'N/A'),
                "cost": k['cost']
            }
            for k in sorted(low_qs_keywords, key=lambda x: x['cost'], reverse=True)[:5]
        ]
    }


def calculate_roi_impact(recommendations, metrics_summary):
    """
    Calculate expected ROI from implementing recommendations.
    """
    savings = 0
    additional_spend = 0
    additional_conversions = 0

    avg_cpa = metrics_summary.get('total_cost', 0) / max(metrics_summary.get('total_conversions', 1), 1)

    for rec in recommendations:
        rec_type = rec.get('type')

        if rec_type == 'keyword_action' and rec.get('action') == 'pause':
            # Savings from pausing underperformers
            # Estimate: keyword wasted ~30% of daily spend, extrapolate to monthly
            estimated_monthly_waste = 100  # Conservative estimate per keyword
            savings += estimated_monthly_waste

        elif rec_type == 'bid_adjustment':
            current_bid = rec.get('current_bid', 0)
            suggested_bid = rec.get('suggested_bid', 0)

            if suggested_bid > current_bid:
                # Increasing bid - estimate additional conversions
                bid_increase_pct = (suggested_bid - current_bid) / current_bid if current_bid > 0 else 0
                # Conservative: 50% of bid increase translates to conversion increase
                conv_increase = bid_increase_pct * 0.5
                additional_conversions += conv_increase * 4  # Per month estimate
                additional_spend += conv_increase * 4 * avg_cpa
            else:
                # Decreasing bid - savings
                bid_decrease = current_bid - suggested_bid
                monthly_savings = bid_decrease * 30 * 10  # Rough estimate
                savings += monthly_savings

    # Add negative keyword savings
    neg_keyword_recs = [r for r in recommendations if r.get('type') == 'keyword_action' and r.get('action') == 'add_negative']
    if neg_keyword_recs:
        # Each negative keyword saves ~RM 50-100/month in wasted clicks
        savings += len(neg_keyword_recs) * 75

    # Estimate revenue (assuming avg customer value)
    avg_customer_value = 200  # Default assumption - should be customized
    estimated_revenue = additional_conversions * avg_customer_value

    net_benefit = savings + estimated_revenue - additional_spend
    roi = (net_benefit / max(additional_spend, 1)) if additional_spend > 0 else 0

    return {
        "monthly_savings": savings,
        "additional_monthly_spend": additional_spend,
        "additional_monthly_conversions": additional_conversions,
        "estimated_monthly_revenue": estimated_revenue,
        "net_monthly_benefit": net_benefit,
        "roi_multiplier": roi,
        "breakdown": {
            "pause_underperformers": savings * 0.6,  # Rough allocation
            "negative_keywords": len(neg_keyword_recs) * 75,
            "bid_optimizations": estimated_revenue
        }
    }


def generate_conversion_value_alert(metrics_summary):
    """Generate alert if conversion value tracking is not set up."""
    total_conv_value = metrics_summary.get('total_conversion_value', 0)
    total_conversions = metrics_summary.get('total_conversions', 0)

    if total_conversions > 0 and total_conv_value == 0:
        return {
            "alert_type": "CRITICAL",
            "issue": "No Conversion Value Tracking",
            "impact": "Cannot calculate true ROAS or optimize for revenue",
            "description": "Your account has conversions but no conversion values assigned. This means you're optimizing for quantity, not quality of conversions.",
            "consequences": [
                "Cannot identify which keywords drive highest-value customers",
                "May be wasting budget on low-value conversions",
                "Unable to use Target ROAS bidding strategy",
                "Missing revenue attribution data"
            ],
            "fix_steps": [
                "Go to Google Ads > Tools & Settings > Conversions",
                "Edit each conversion action",
                "Set 'Value' to either:",
                "  - Same value for each conversion (e.g., RM 200 avg order)",
                "  - Different value per conversion (pass actual transaction value)",
                "Test with Google Tag Assistant",
                "Wait 24-48 hours for data to populate"
            ],
            "estimated_time": "15-30 minutes",
            "priority": 1
        }

    return None


def main():
    """Example usage"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python analyze_advanced_insights.py <metrics_file>")
        sys.exit(1)

    with open(sys.argv[1], 'r') as f:
        metrics = json.load(f)

    # Run analyses
    search_analysis = analyze_search_queries(
        metrics.get('search_queries', []),
        metrics.get('keywords', [])
    )

    qs_roadmap = generate_quality_score_roadmap(metrics.get('keywords', []))

    print(json.dumps({
        "search_query_analysis": search_analysis,
        "quality_score_roadmap": qs_roadmap
    }, indent=2))


if __name__ == "__main__":
    main()
