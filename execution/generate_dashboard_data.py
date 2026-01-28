"""
Generate comprehensive dashboard data.json from metrics and insights
"""
import json
from datetime import datetime
from collections import defaultdict
import os

def generate_dashboard_data(metrics_file, recs_file, output_file):
    # Load the metrics
    with open(metrics_file, 'r') as f:
        metrics = json.load(f)

    # Load recommendations
    with open(recs_file, 'r') as f:
        recs_list = json.load(f)

    # === CAMPAIGNS ===
    campaigns = metrics.get('campaigns', [])
    active_campaigns = [c for c in campaigns if c.get('cost', 0) > 0]

    # === KEYWORDS ===
    keywords = metrics.get('keywords', [])
    valid_qs = [k.get('quality_score', 0) for k in keywords if k.get('quality_score', 0) > 0]
    avg_qs = sum(valid_qs) / len(valid_qs) if valid_qs else 0
    low_qs_keywords = [k for k in keywords if 0 < k.get('quality_score', 0) < 5]

    # === SEARCH QUERIES ANALYSIS ===
    search_queries = metrics.get('search_queries', [])
    wasted_queries = [sq for sq in search_queries if sq.get('conversions', 0) == 0 and sq.get('cost', 0) > 10]
    total_wasted = sum(sq.get('cost', 0) for sq in wasted_queries)

    # === TIME PERFORMANCE ===
    time_data = metrics.get('time_performance', [])
    hourly_perf = defaultdict(lambda: {'clicks': 0, 'conversions': 0, 'cost': 0})
    daily_perf = defaultdict(lambda: {'clicks': 0, 'conversions': 0, 'cost': 0})

    for t in time_data:
        hour = t.get('hour', 0)
        day = t.get('day_of_week', 'UNKNOWN')
        hourly_perf[hour]['clicks'] += t.get('clicks', 0)
        hourly_perf[hour]['conversions'] += t.get('conversions', 0)
        hourly_perf[hour]['cost'] += t.get('cost', 0)
        daily_perf[day]['clicks'] += t.get('clicks', 0)
        daily_perf[day]['conversions'] += t.get('conversions', 0)
        daily_perf[day]['cost'] += t.get('cost', 0)

    best_hour = max(hourly_perf.items(), key=lambda x: x[1]['clicks'])[0] if hourly_perf else None
    best_day = max(daily_perf.items(), key=lambda x: x[1]['clicks'])[0] if daily_perf else None

    # === SUMMARY ===
    total_spend = sum(c.get('cost', 0) for c in campaigns)
    total_impressions = sum(c.get('impressions', 0) for c in campaigns)
    total_clicks = sum(c.get('clicks', 0) for c in campaigns)
    total_conversions = sum(c.get('conversions', 0) for c in campaigns)

    # === BUILD DASHBOARD DATA ===
    dashboard_data = {
        'customer_id': '7867388610',
        'account_name': 'YCK Chiropractic',
        'generated_at': datetime.now().isoformat(),
        'date_range': metrics.get('date_range', {'start': '2024-12-29', 'end': '2025-01-28'}),
        'summary': {
            'total_spend': round(total_spend, 2),
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'total_conversions': round(total_conversions, 2),
            'cost_per_conversion': round(total_spend / total_conversions, 2) if total_conversions > 0 else 0,
            'avg_ctr': round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0,
            'avg_quality_score': round(avg_qs, 1)
        },
        'trends': {
            'spend_change': 0,
            'conversions_change': 0,
            'cpa_change': 0,
            'quality_score_change': 0
        },
        'campaigns': [
            {
                'name': c.get('name', 'Unknown'),
                'status': c.get('status', 'UNKNOWN'),
                'spend': round(c.get('cost', 0), 2),
                'impressions': c.get('impressions', 0),
                'clicks': c.get('clicks', 0),
                'ctr': round(c.get('ctr', 0) * 100, 2) if c.get('ctr', 0) < 1 else round(c.get('ctr', 0), 2),
                'conversions': round(c.get('conversions', 0), 2),
                'cpa': round(c.get('cost_per_conversion', 0), 2)
            }
            for c in sorted(active_campaigns, key=lambda x: x.get('cost', 0), reverse=True)
        ],
        'keywords': [
            {
                'keyword': k.get('keyword_text', 'Unknown'),
                'campaign': k.get('campaign_name', '-'),
                'impressions': k.get('impressions', 0),
                'clicks': k.get('clicks', 0),
                'ctr': round(k.get('ctr', 0) * 100, 2) if k.get('ctr', 0) < 1 else round(k.get('ctr', 0), 2),
                'avg_cpc': round(k.get('avg_cpc', 0), 2),
                'quality_score': k.get('quality_score', 0)
            }
            for k in sorted(keywords, key=lambda x: x.get('impressions', 0), reverse=True)[:15]
        ],
        'search_queries': [
            {
                'query': sq.get('search_term', ''),
                'campaign': sq.get('campaign_name', ''),
                'impressions': sq.get('impressions', 0),
                'clicks': sq.get('clicks', 0),
                'cost': round(sq.get('cost', 0), 2),
                'conversions': sq.get('conversions', 0)
            }
            for sq in sorted(search_queries, key=lambda x: x.get('clicks', 0), reverse=True)[:10]
        ],
        'geo_performance': [
            {
                'location_name': geo.get('location_name', ''),
                'country_criterion_id': geo.get('country_criterion_id'),
                'location_type': geo.get('location_type', ''),
                'campaign_name': geo.get('campaign_name', ''),
                'impressions': geo.get('impressions', 0),
                'clicks': geo.get('clicks', 0),
                'ctr': geo.get('ctr', 0),
                'cost': round(geo.get('cost', 0), 2),
                'conversions': geo.get('conversions', 0)
            }
            for geo in sorted(metrics.get('geo_performance', []), key=lambda x: x.get('clicks', 0), reverse=True)[:10]
        ],
        'insights': [],
        'recommendations': []
    }

    # Add insights
    dashboard_data['insights'].append({
        'type': 'warning',
        'title': 'Low Quality Scores',
        'description': f'{len(low_qs_keywords)} keywords have quality scores below 5. Improving ad relevance and landing pages could reduce CPC by 20-30%.'
    })

    dashboard_data['insights'].append({
        'type': 'alert',
        'title': 'Wasted Ad Spend',
        'description': f'RM {total_wasted:,.2f} spent on {len(wasted_queries)} search queries with zero conversions. Consider adding negative keywords.'
    })

    if best_hour is not None:
        dashboard_data['insights'].append({
            'type': 'opportunity',
            'title': f'Best Performing Hour: {best_hour}:00',
            'description': f'Hour {best_hour}:00 generates the most clicks ({hourly_perf[best_hour]["clicks"]:,}). Consider increasing bids during peak hours.'
        })

    if best_day:
        day_name = best_day.title() if best_day else 'N/A'
        dashboard_data['insights'].append({
            'type': 'opportunity',
            'title': f'Best Performing Day: {day_name}',
            'description': f'{day_name} generates the most engagement ({daily_perf[best_day]["clicks"]:,} clicks). Consider dayparting strategy.'
        })

    dashboard_data['insights'].append({
        'type': 'info',
        'title': 'Campaign Status',
        'description': f'All campaigns are currently PAUSED. Total historical spend: RM {total_spend:,.2f}.'
    })

    if total_conversions > 0:
        dashboard_data['insights'].append({
            'type': 'alert',
            'title': 'High CPA Alert',
            'description': f'Cost per conversion is RM {total_spend / total_conversions:,.2f}. Review conversion tracking and keyword targeting.'
        })
    else:
        dashboard_data['insights'].append({
            'type': 'alert',
            'title': 'No Conversions',
            'description': 'No conversions recorded. Verify conversion tracking is set up correctly in Google Ads.'
        })

    # Add recommendations with action data
    for rec in recs_list[:8]:
        action = rec.get('action', 'review').replace('_', ' ').title()
        keyword = rec.get('keyword', '')
        target = rec.get('target', '')

        dashboard_data['recommendations'].append({
            'title': f'{action}: {keyword}' if keyword else action,
            'description': rec.get('reason', ''),
            'impact': 'High' if 'wasted' in rec.get('reason', '').lower() else 'Medium',
            'action_type': rec.get('type', 'review'),
            'target_id': target,
            'keyword': keyword,
            'suggested_action': rec.get('suggested', '')
        })

    # Save
    with open(output_file, 'w') as f:
        json.dump(dashboard_data, f, indent=2)

    print('Updated data.json with comprehensive insights:')
    print(f'  Campaigns: {len(dashboard_data["campaigns"])}')
    print(f'  Keywords: {len(dashboard_data["keywords"])}')
    print(f'  Search Queries: {len(dashboard_data["search_queries"])}')
    print(f'  Insights: {len(dashboard_data["insights"])}')
    print(f'  Recommendations: {len(dashboard_data["recommendations"])}')
    print()
    print('Insights added:')
    for i in dashboard_data['insights']:
        print(f'  - [{i["type"]}] {i["title"]}')

    return dashboard_data


if __name__ == '__main__':
    import glob

    # Find latest metrics file
    metrics_files = glob.glob('.tmp/google_ads_metrics_7867388610_*.json')
    if not metrics_files:
        print('No metrics file found!')
        exit(1)

    latest_metrics = max(metrics_files)
    print(f'Using metrics: {latest_metrics}')

    generate_dashboard_data(
        latest_metrics,
        '.tmp/recommendations_enhanced_7867388610.json',
        'netlify-dashboard/data.json'
    )
