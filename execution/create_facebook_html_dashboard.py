#!/usr/bin/env python3
"""
Create an HTML dashboard with Facebook/Meta Ads insights and recommendations.

Mirrors create_html_dashboard.py (Google Ads version) with Facebook-specific
sections: demographics, placements, creative fatigue, frequency analysis.

Usage:
    python execution/create_facebook_html_dashboard.py \
        --metrics_file .tmp/facebook_ads_metrics_XXXXX.json \
        --insights_file .tmp/facebook_insights_XXXXX.json \
        --recommendations_file .tmp/facebook_recommendations_XXXXX.json

    # Or auto-detect:
    python execution/create_facebook_html_dashboard.py --ad_account_id XXXXX
"""

import argparse
import json
import glob
import os
from datetime import datetime
from calculate_total_impact import aggregate_total_benefits


def create_facebook_html_dashboard(metrics, insights, recommendations, output_file):
    """Generate a standalone HTML dashboard for Facebook Ads."""

    summary = metrics.get('summary', {})
    date_range = metrics.get('date_range', {})
    currency = metrics.get('currency', 'MYR')
    cs = 'RM' if currency == 'MYR' else '$' if currency == 'USD' else currency
    account_name = metrics.get('account_name', 'Facebook Ads')

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Ads Insights - {account_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f0f2f5;
            padding: 20px;
            color: #1c1e21;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            padding: 20px 0 30px;
            border-bottom: 3px solid #1877F2;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #1877F2;
            font-size: 28px;
            margin-bottom: 5px;
        }}
        .header .subtitle {{
            color: #65676b;
            font-size: 14px;
        }}
        .header .account-name {{
            font-size: 18px;
            color: #1c1e21;
            margin-top: 5px;
        }}
        .platform-badge {{
            display: inline-block;
            background: #1877F2;
            color: white;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 10px;
        }}

        /* Metric cards */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            padding: 20px;
            border-radius: 10px;
            color: white;
            text-align: center;
        }}
        .metric-card h3 {{ font-size: 12px; opacity: 0.9; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; }}
        .metric-card .value {{ font-size: 26px; font-weight: 700; }}
        .metric-card .sub {{ font-size: 11px; opacity: 0.8; margin-top: 4px; }}
        .bg-blue {{ background: linear-gradient(135deg, #1877F2, #0d47a1); }}
        .bg-green {{ background: linear-gradient(135deg, #42b72a, #2e7d32); }}
        .bg-orange {{ background: linear-gradient(135deg, #f5a623, #e65100); }}
        .bg-purple {{ background: linear-gradient(135deg, #8b5cf6, #6d28d9); }}
        .bg-teal {{ background: linear-gradient(135deg, #06b6d4, #0e7490); }}
        .bg-pink {{ background: linear-gradient(135deg, #ec4899, #be185d); }}
        .bg-amber {{ background: linear-gradient(135deg, #f59e0b, #d97706); }}

        /* Sections */
        .section {{ margin-bottom: 30px; }}
        .section h2 {{
            color: #1877F2;
            font-size: 20px;
            margin-bottom: 5px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e4e6eb;
        }}
        .section .description {{
            color: #65676b;
            font-size: 13px;
            margin-bottom: 15px;
        }}

        /* AI Summary */
        .ai-summary {{
            background: #f0f7ff;
            border-left: 4px solid #1877F2;
            padding: 20px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 30px;
            line-height: 1.7;
            color: #1c1e21;
        }}

        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            background: #f0f2f5;
            color: #65676b;
            padding: 10px 8px;
            text-align: left;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        td {{
            padding: 10px 8px;
            border-bottom: 1px solid #e4e6eb;
        }}
        tr:hover {{ background: #f7f8fa; }}
        .text-right {{ text-align: right; }}

        /* Status badges */
        .status {{ padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
        .status-active {{ background: #e6f4ea; color: #1e7e34; }}
        .status-paused {{ background: #fef3cd; color: #856404; }}
        .status-other {{ background: #e4e6eb; color: #65676b; }}

        /* Fatigue indicators */
        .fatigue-healthy {{ color: #42b72a; }}
        .fatigue-warning {{ color: #f5a623; font-weight: 600; }}
        .fatigue-critical {{ color: #fa3e3e; font-weight: 700; }}

        /* Color-coded values */
        .color-good {{ color: #42b72a; font-weight: 600; }}
        .color-ok {{ color: #f5a623; font-weight: 600; }}
        .color-bad {{ color: #fa3e3e; font-weight: 600; }}

        /* Recommendation cards */
        .rec-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 15px; }}
        .rec-card {{
            border: 1px solid #e4e6eb;
            border-radius: 8px;
            padding: 18px;
            transition: box-shadow 0.2s;
        }}
        .rec-card:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,0.1); }}
        .rec-card .rec-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .rec-card h4 {{ font-size: 14px; color: #1c1e21; }}
        .rec-card p {{ font-size: 13px; color: #65676b; line-height: 1.5; margin-bottom: 8px; }}
        .rec-card .impact {{ font-size: 12px; color: #65676b; font-style: italic; }}
        .priority-high {{ border-left: 4px solid #fa3e3e; }}
        .priority-medium {{ border-left: 4px solid #f5a623; }}
        .priority-low {{ border-left: 4px solid #42b72a; }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .badge-high {{ background: #fde8e8; color: #fa3e3e; }}
        .badge-medium {{ background: #fef3cd; color: #e65100; }}
        .badge-low {{ background: #e6f4ea; color: #42b72a; }}

        /* Automation badges */
        .automation-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: 700;
            margin-left: 5px;
        }}
        .badge-auto {{
            background: #e6f4ea;
            color: #1e7e34;
            border: 1px solid #42b72a;
        }}
        .badge-manual {{
            background: #fef3cd;
            color: #856404;
            border: 1px solid #f5a623;
        }}

        /* Confidence badges */
        .confidence-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 9px;
            font-weight: 600;
            margin-left: 5px;
        }}
        .conf-high {{
            background: #d4edda;
            color: #155724;
        }}
        .conf-moderate {{
            background: #fff3cd;
            color: #856404;
        }}

        /* Total impact section */
        .total-impact-summary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
        }}
        .total-impact-summary h2 {{
            color: white;
            border-bottom: 2px solid rgba(255,255,255,0.3);
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .total-impact-summary .metrics-grid {{
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        }}
        .total-impact-summary .metric-card {{
            background: rgba(255,255,255,0.15);
        }}
        .total-impact-summary .sub {{
            opacity: 0.9;
        }}

        /* Manual explanation */
        .manual-explanation {{
            background: #fff3cd;
            border-left: 3px solid #ffc107;
            padding: 10px;
            margin-top: 10px;
            font-size: 13px;
            color: #856404;
        }}

        /* Formula display */
        .formula-explain {{
            background: #f8f9fa;
            border-left: 3px solid #1877F2;
            padding: 8px;
            margin-top: 8px;
            font-size: 12px;
            font-family: 'Courier New', monospace;
            color: #495057;
        }}

        /* Demographics heatmap */
        .demo-grid {{
            display: grid;
            grid-template-columns: auto repeat(3, 1fr);
            gap: 2px;
            font-size: 12px;
        }}
        .demo-cell {{
            padding: 8px;
            text-align: center;
            border-radius: 4px;
        }}
        .demo-header {{ background: #f0f2f5; font-weight: 600; color: #65676b; }}
        .demo-label {{ background: #f0f2f5; font-weight: 600; text-align: left; padding-left: 12px; }}

        /* Scroll wrapper for tables */
        .table-wrapper {{ overflow-x: auto; }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 20px 0;
            color: #65676b;
            font-size: 12px;
            border-top: 1px solid #e4e6eb;
            margin-top: 30px;
        }}

        /* Print */
        @media print {{
            body {{ padding: 0; background: white; }}
            .container {{ box-shadow: none; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
<div class="container">

    <!-- Header -->
    <div class="header">
        <span class="platform-badge">FACEBOOK / META ADS</span>
        <h1>Ads Insights Dashboard</h1>
        <div class="account-name">{account_name}</div>
        <div class="subtitle">
            {date_range.get('start_date', 'N/A')} to {date_range.get('end_date', 'N/A')}
            &nbsp;|&nbsp; Account: {metrics.get('ad_account_id', '')}
        </div>
    </div>

    <!-- Key Metrics -->
    <div class="metrics-grid">
        <div class="metric-card bg-blue">
            <h3>Total Spend</h3>
            <div class="value">{cs} {summary.get('total_spend', 0):,.2f}</div>
        </div>
        <div class="metric-card bg-green">
            <h3>Conversions</h3>
            <div class="value">{summary.get('total_conversions', 0):,}</div>
            <div class="sub">CPA: {cs} {summary.get('overall_cpa', 0):,.2f}</div>
        </div>
        <div class="metric-card bg-purple">
            <h3>Reach</h3>
            <div class="value">{summary.get('total_reach', 0):,}</div>
            <div class="sub">Unique people</div>
        </div>
        <div class="metric-card bg-amber">
            <h3>Frequency</h3>
            <div class="value">{summary.get('total_frequency', 0):.1f}x</div>
            <div class="sub">{'&#9888; High' if summary.get('total_frequency', 0) > 3 else 'Avg impressions/person'}</div>
        </div>
        <div class="metric-card bg-teal">
            <h3>CTR</h3>
            <div class="value">{summary.get('overall_ctr', 0):.2f}%</div>
            <div class="sub">{'Below avg' if summary.get('overall_ctr', 0) < 1 else 'Good' if summary.get('overall_ctr', 0) >= 2 else 'Average'}</div>
        </div>
        <div class="metric-card bg-pink">
            <h3>CPM</h3>
            <div class="value">{cs} {summary.get('overall_cpm', 0):,.2f}</div>
            <div class="sub">Cost per 1,000 impressions</div>
        </div>
        <div class="metric-card bg-orange">
            <h3>Clicks</h3>
            <div class="value">{summary.get('total_clicks', 0):,}</div>
            <div class="sub">CPC: {cs} {summary.get('overall_cpc', 0):,.2f}</div>
        </div>
    </div>
"""

    # AI Summary
    insights_summary = insights.get('summary', '')
    if insights_summary:
        html += f"""
    <div class="ai-summary">
        <strong>&#129302; AI Insights Summary</strong><br><br>
        {insights_summary}
    </div>
"""

    # Campaign Performance
    campaigns = metrics.get('campaigns', [])
    if campaigns:
        html += """
    <div class="section">
        <h2>Campaign Performance</h2>
        <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Campaign</th>
                    <th>Status</th>
                    <th>Objective</th>
                    <th class="text-right">Spend</th>
                    <th class="text-right">Reach</th>
                    <th class="text-right">Freq</th>
                    <th class="text-right">Clicks</th>
                    <th class="text-right">CTR</th>
                    <th class="text-right">Conv</th>
                    <th class="text-right">CPA</th>
                </tr>
            </thead>
            <tbody>
"""
        for c in campaigns[:20]:
            status = c.get('status', 'UNKNOWN')
            status_class = 'status-active' if 'ACTIVE' in status.upper() else (
                'status-paused' if 'PAUSED' in status.upper() else 'status-other'
            )
            cpa = c.get('cost_per_conversion', 0)
            cpa_class = 'color-good' if 0 < cpa < 50 else ('color-ok' if cpa < 100 else 'color-bad')

            html += f"""
                <tr>
                    <td><strong>{c.get('campaign_name', '')}</strong></td>
                    <td><span class="status {status_class}">{status}</span></td>
                    <td>{c.get('objective', '').replace('OUTCOME_', '').title()}</td>
                    <td class="text-right">{cs} {c.get('spend', 0):,.2f}</td>
                    <td class="text-right">{c.get('reach', 0):,}</td>
                    <td class="text-right">{c.get('frequency', 0):.1f}</td>
                    <td class="text-right">{c.get('clicks', 0):,}</td>
                    <td class="text-right">{c.get('ctr', 0):.2f}%</td>
                    <td class="text-right">{c.get('conversions', 0)}</td>
                    <td class="text-right {cpa_class}">{cs} {cpa:,.2f}</td>
                </tr>
"""
        html += """
            </tbody>
        </table>
        </div>
    </div>
"""

    # Ad Set Performance
    ad_sets = metrics.get('ad_sets', [])
    if ad_sets:
        html += """
    <div class="section">
        <h2>Ad Set Performance</h2>
        <p class="description">Ad sets with their targeting summary and performance metrics.</p>
        <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Ad Set</th>
                    <th>Campaign</th>
                    <th>Targeting</th>
                    <th class="text-right">Spend</th>
                    <th class="text-right">Clicks</th>
                    <th class="text-right">CTR</th>
                    <th class="text-right">Conv</th>
                    <th class="text-right">CPA</th>
                </tr>
            </thead>
            <tbody>
"""
        for a in ad_sets[:15]:
            targeting = a.get('targeting_summary', '')
            if len(targeting) > 80:
                targeting = targeting[:77] + '...'

            cpa = a.get('cost_per_conversion', 0)
            html += f"""
                <tr>
                    <td><strong>{a.get('adset_name', '')}</strong></td>
                    <td>{a.get('campaign_name', '')}</td>
                    <td style="font-size:11px;color:#65676b;">{targeting}</td>
                    <td class="text-right">{cs} {a.get('spend', 0):,.2f}</td>
                    <td class="text-right">{a.get('clicks', 0):,}</td>
                    <td class="text-right">{a.get('ctr', 0):.2f}%</td>
                    <td class="text-right">{a.get('conversions', 0)}</td>
                    <td class="text-right">{cs} {cpa:,.2f}</td>
                </tr>
"""
        html += """
            </tbody>
        </table>
        </div>
    </div>
"""

    # Placement Performance
    placement_data = insights.get('placement_efficiency', {})
    placements = placement_data.get('placements', [])
    if placements:
        html += """
    <div class="section">
        <h2>Placement Performance</h2>
        <p class="description">Performance across Facebook, Instagram, Audience Network, and Messenger.</p>
        <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Placement</th>
                    <th class="text-right">Spend</th>
                    <th class="text-right">Clicks</th>
                    <th class="text-right">CTR</th>
                    <th class="text-right">CPM</th>
                    <th class="text-right">Conv</th>
                    <th class="text-right">CPA</th>
                    <th>Efficiency</th>
                </tr>
            </thead>
            <tbody>
"""
        for pl in placements:
            eff = pl.get('efficiency', 'average')
            eff_class = 'color-good' if eff == 'good' else ('color-bad' if eff == 'poor' else 'color-ok')

            html += f"""
                <tr>
                    <td><strong>{pl.get('placement_name', '')}</strong></td>
                    <td class="text-right">{cs} {pl.get('spend', 0):,.2f}</td>
                    <td class="text-right">{pl.get('clicks', 0):,}</td>
                    <td class="text-right">{pl.get('ctr', 0):.2f}%</td>
                    <td class="text-right">{cs} {pl.get('cpm', 0):,.2f}</td>
                    <td class="text-right">{pl.get('conversions', 0)}</td>
                    <td class="text-right">{cs} {pl.get('cpa', 0):,.2f}</td>
                    <td><span class="{eff_class}">{eff.title()}</span></td>
                </tr>
"""
        html += """
            </tbody>
        </table>
        </div>
    </div>
"""

    # Demographic Breakdown
    demographics = metrics.get('demographic_breakdown', [])
    if demographics:
        # Build age × gender matrix
        age_groups = sorted(set(d.get('age', '') for d in demographics))
        genders = sorted(set(d.get('gender', '') for d in demographics))

        html += """
    <div class="section">
        <h2>Demographic Performance</h2>
        <p class="description">Spend and conversions by age and gender. Red = high spend, no conversions.</p>
        <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Age / Gender</th>
"""
        for g in genders:
            html += f'                    <th class="text-right">{g.title()} Spend</th>\n'
            html += f'                    <th class="text-right">{g.title()} Conv</th>\n'
        html += """
                </tr>
            </thead>
            <tbody>
"""
        # Build lookup
        demo_lookup = {}
        for d in demographics:
            key = (d.get('age', ''), d.get('gender', ''))
            demo_lookup[key] = d

        for age in age_groups:
            html += f'                <tr>\n                    <td><strong>{age}</strong></td>\n'
            for g in genders:
                d = demo_lookup.get((age, g), {})
                spend = d.get('spend', 0)
                conv = d.get('conversions', 0)
                color = 'color-bad' if spend > 5 and conv == 0 else ('color-good' if conv > 0 else '')
                html += f'                    <td class="text-right {color}">{cs} {spend:,.2f}</td>\n'
                html += f'                    <td class="text-right">{conv}</td>\n'
            html += '                </tr>\n'

        html += """
            </tbody>
        </table>
        </div>
    </div>
"""

    # Creative Fatigue
    fatigue_data = insights.get('creative_fatigue', {})
    fatigued_ads = fatigue_data.get('fatigued_ads', [])
    if fatigued_ads:
        html += """
    <div class="section">
        <h2>Creative Fatigue Analysis</h2>
        <p class="description">Ads with high frequency showing signs of audience fatigue. Consider refreshing creatives.</p>
        <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Ad Name</th>
                    <th>Campaign</th>
                    <th class="text-right">Frequency</th>
                    <th class="text-right">CTR</th>
                    <th class="text-right">Spend</th>
                    <th>Severity</th>
                    <th>Issues</th>
                </tr>
            </thead>
            <tbody>
"""
        for ad in fatigued_ads[:10]:
            sev = ad.get('fatigue_level', 'warning')
            sev_class = f'fatigue-{sev}'
            issues_str = '; '.join(ad.get('issues', []))
            html += f"""
                <tr>
                    <td><strong>{ad.get('ad_name', '')[:40]}</strong></td>
                    <td>{ad.get('campaign_name', '')}</td>
                    <td class="text-right {sev_class}">{ad.get('frequency', 0):.1f}x</td>
                    <td class="text-right">{ad.get('ctr', 0):.2f}%</td>
                    <td class="text-right">{cs} {ad.get('spend', 0):,.2f}</td>
                    <td><span class="{sev_class}">{sev.upper()}</span></td>
                    <td style="font-size:11px;">{issues_str[:80]}</td>
                </tr>
"""
        html += """
            </tbody>
        </table>
        </div>
    </div>
"""

    # Geographic Performance
    geo_data = insights.get('geo_performance', {})
    locations = geo_data.get('locations', [])
    if locations:
        html += """
    <div class="section">
        <h2>Geographic Performance</h2>
        <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Location</th>
                    <th class="text-right">Clicks</th>
                    <th class="text-right">Spend</th>
                    <th class="text-right">Conv</th>
                    <th class="text-right">CPA</th>
                </tr>
            </thead>
            <tbody>
"""
        for loc in locations[:15]:
            conv = loc.get('conversions', 0)
            spend = loc.get('spend', 0)
            cpa = spend / conv if conv > 0 else 0
            cpa_display = f'{cs} {cpa:,.2f}' if conv > 0 else '-'
            cpa_class = 'color-bad' if spend > 5 and conv == 0 else ''

            html += f"""
                <tr>
                    <td><strong>{loc.get('location_name', '')}</strong></td>
                    <td class="text-right">{loc.get('clicks', 0):,}</td>
                    <td class="text-right {cpa_class}">{cs} {spend:,.2f}</td>
                    <td class="text-right">{conv}</td>
                    <td class="text-right">{cpa_display}</td>
                </tr>
"""
        html += """
            </tbody>
        </table>
        </div>
    </div>
"""

    # Time Performance
    time_data = insights.get('time_performance', {})
    hourly = time_data.get('hourly_performance', [])
    daily = time_data.get('daily_performance', [])

    if hourly:
        html += """
    <div class="section">
        <h2>Time Performance</h2>
        <p class="description">Hourly and daily performance patterns.</p>
"""
        # Hourly table
        html += """
        <h3 style="font-size:15px;margin:10px 0;">Hourly Performance</h3>
        <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Hour</th>
                    <th class="text-right">Clicks</th>
                    <th class="text-right">Spend</th>
                    <th class="text-right">Conv</th>
                    <th class="text-right">CPA</th>
                </tr>
            </thead>
            <tbody>
"""
        for h in hourly:
            if h.get('clicks', 0) > 0 or h.get('spend', 0) > 0:
                conv = h.get('conversions', 0)
                spend = h.get('spend', 0)
                cpa_display = f"{cs} {h['cpa']:,.2f}" if conv > 0 else '-'
                html += f"""
                <tr>
                    <td><strong>{h.get('hour_label', '')}</strong></td>
                    <td class="text-right">{h.get('clicks', 0):,}</td>
                    <td class="text-right">{cs} {spend:,.2f}</td>
                    <td class="text-right">{conv}</td>
                    <td class="text-right">{cpa_display}</td>
                </tr>
"""
        html += """
            </tbody>
        </table>
        </div>
"""

    if daily:
        html += """
        <h3 style="font-size:15px;margin:15px 0 10px;">Day of Week Performance</h3>
        <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Day</th>
                    <th class="text-right">Clicks</th>
                    <th class="text-right">Spend</th>
                    <th class="text-right">Conv</th>
                    <th class="text-right">CPA</th>
                </tr>
            </thead>
            <tbody>
"""
        for d in daily:
            conv = d.get('conversions', 0)
            cpa_display = f"{cs} {d['cpa']:,.2f}" if conv > 0 else '-'
            html += f"""
                <tr>
                    <td><strong>{d.get('day', '')}</strong></td>
                    <td class="text-right">{d.get('clicks', 0):,}</td>
                    <td class="text-right">{cs} {d.get('spend', 0):,.2f}</td>
                    <td class="text-right">{conv}</td>
                    <td class="text-right">{cpa_display}</td>
                </tr>
"""
        html += """
            </tbody>
        </table>
        </div>
    </div>
"""

    # Recommendations
    if recommendations:
        # Calculate total impact
        totals = aggregate_total_benefits(recommendations, confidence_level='moderate')

        # Total Impact Summary
        html += f"""
    <div class="total-impact-summary">
        <h2>📊 Total Expected Impact</h2>
        <p style="opacity: 0.9; margin-bottom: 20px;">
            Aggregate projected benefits from implementing all {totals['total_recommendations']} recommendations.
            Using <strong>moderate</strong> confidence (70% of maximum).
        </p>
        <div class="metrics-grid">
            <div class="metric-card">
                <h3>Monthly Savings</h3>
                <div class="value">{cs} {totals['total_monthly_savings']:,.0f}</div>
                <div class="sub">From eliminating waste</div>
            </div>
            <div class="metric-card">
                <h3>Additional Conversions</h3>
                <div class="value">{totals['total_additional_conversions']:.0f}</div>
                <div class="sub">Monthly projection</div>
            </div>
            <div class="metric-card">
                <h3>Additional Revenue</h3>
                <div class="value">{cs} {totals['total_additional_revenue']:,.0f}</div>
                <div class="sub">From scaling winners</div>
            </div>
            <div class="metric-card">
                <h3>Net Monthly Benefit</h3>
                <div class="value">{cs} {totals['total_net_benefit']:,.0f}</div>
                <div class="sub">Total value unlock</div>
            </div>
        </div>
        <p style="margin-top: 20px; font-size: 13px; opacity: 0.85;">
            <strong>Automation Status:</strong> {totals['automatable_count']} auto-actionable, {totals['manual_count']} manual required
        </p>
    </div>

    <div class="section">
        <h2>Optimization Recommendations</h2>
        <p class="description">Actionable recommendations sorted by priority. Apply these to improve performance.</p>
        <div class="rec-grid">
"""
        for i, rec in enumerate(recommendations[:12], 1):
            priority = rec.get('priority', 'medium')
            automation = rec.get('automation', {})
            is_automatable = automation.get('is_automatable', False)
            manual_reason = automation.get('manual_reason')
            impact_data = rec.get('impact_data', {})
            confidence_pct = impact_data.get('confidence_pct', 50)
            confidence_class = 'conf-high' if confidence_pct >= 80 else 'conf-moderate'
            formula = impact_data.get('formula', '')

            auto_badge = '✓ AUTO' if is_automatable else '⚠ MANUAL'
            auto_class = 'badge-auto' if is_automatable else 'badge-manual'

            html += f"""
            <div class="rec-card priority-{priority}">
                <div class="rec-header">
                    <h4>{i}. {rec.get('action', '')}</h4>
                    <div>
                        <span class="badge badge-{priority}">{priority.upper()}</span>
                        <span class="automation-badge {auto_class}">{auto_badge}</span>
                        <span class="confidence-badge {confidence_class}">{confidence_pct}%</span>
                    </div>
                </div>
                <p>{rec.get('reason', '')}</p>
                <div class="impact">Expected: {rec.get('expected_impact', '')}</div>
"""
            if formula:
                html += f"""
                <div class="formula-explain">
                    <span style="margin-right: 5px;">📊</span>{formula}
                </div>
"""
            if manual_reason:
                html += f"""
                <div class="manual-explanation">
                    <strong>Why Manual?</strong> {manual_reason}
                </div>
"""
            html += """
            </div>
"""
        html += """
        </div>
    </div>
"""

    # Landing Page Performance
    lp_data = insights.get('landing_page_performance', {})
    heatmap = lp_data.get('heatmap', [])
    if heatmap:
        html += """
    <div class="section">
        <h2>Landing Page Performance</h2>
        <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>Landing Page URL</th>
                    <th class="text-right">Clicks</th>
                    <th class="text-right">Spend</th>
                    <th class="text-right">Conv</th>
                    <th class="text-right">Conv Rate</th>
                </tr>
            </thead>
            <tbody>
"""
        for lp in heatmap:
            color = lp.get('color', '')
            color_class = f'color-{"good" if color == "green" else "ok" if color == "orange" else "bad"}'
            url_display = lp.get('url', '')
            if len(url_display) > 60:
                url_display = url_display[:57] + '...'

            html += f"""
                <tr>
                    <td>{url_display}</td>
                    <td class="text-right">{lp.get('clicks', 0):,}</td>
                    <td class="text-right">{cs} {lp.get('spend', 0):,.2f}</td>
                    <td class="text-right">{lp.get('conversions', 0)}</td>
                    <td class="text-right {color_class}">{lp.get('conversion_rate', 0):.1f}%</td>
                </tr>
"""
        html += """
            </tbody>
        </table>
        </div>
    </div>
"""

    # Footer
    html += f"""
    <div class="footer">
        <p>Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')} | Facebook Ads Insights Dashboard</p>
        <p style="margin-top:5px;">
            <button class="no-print" onclick="window.print()" style="padding:8px 20px;background:#1877F2;color:white;border:none;border-radius:5px;cursor:pointer;font-size:13px;">
                Print / Save PDF
            </button>
        </p>
    </div>

</div>
</body>
</html>
"""

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"[OK] Dashboard saved: {output_file}")
    return output_file


def main():
    parser = argparse.ArgumentParser(description="Generate Facebook Ads HTML Dashboard")
    parser.add_argument('--metrics_file', help='Path to metrics JSON')
    parser.add_argument('--insights_file', help='Path to insights JSON')
    parser.add_argument('--recommendations_file', help='Path to recommendations JSON')
    parser.add_argument('--ad_account_id', help='Auto-detect files for this account')
    parser.add_argument('--output_dir', default='.tmp', help='Output directory')

    args = parser.parse_args()

    # Auto-detect files if ad_account_id provided
    if args.ad_account_id and not args.metrics_file:
        clean_id = args.ad_account_id.replace('act_', '')
        metrics_files = glob.glob(f'.tmp/facebook_ads_metrics_{clean_id}_*.json')
        if metrics_files:
            # Sort by modification time, get the most recent
            args.metrics_file = max(metrics_files, key=os.path.getmtime)
        args.insights_file = args.insights_file or f'.tmp/facebook_insights_{clean_id}.json'
        args.recommendations_file = args.recommendations_file or f'.tmp/facebook_recommendations_{clean_id}.json'
    elif not args.metrics_file:
        # Try auto-detect any
        metrics_files = glob.glob('.tmp/facebook_ads_metrics_*.json')
        if metrics_files:
            # Sort by modification time, get the most recent
            args.metrics_file = max(metrics_files, key=os.path.getmtime)
            # Extract account ID
            fname = os.path.basename(args.metrics_file)
            parts = fname.replace('facebook_ads_metrics_', '').split('_')
            clean_id = parts[0] if parts else ''
            args.insights_file = args.insights_file or f'.tmp/facebook_insights_{clean_id}.json'
            args.recommendations_file = args.recommendations_file or f'.tmp/facebook_recommendations_{clean_id}.json'

    if not args.metrics_file or not os.path.exists(args.metrics_file):
        print("[ERROR] Metrics file not found. Run fetch_facebook_ads_metrics.py first.")
        return

    # Load files
    with open(args.metrics_file, 'r') as f:
        metrics = json.load(f)

    insights = {}
    if args.insights_file and os.path.exists(args.insights_file):
        with open(args.insights_file, 'r') as f:
            insights = json.load(f)
    else:
        print("[WARNING] Insights file not found. Dashboard will have limited analysis.")

    recommendations = []
    if args.recommendations_file and os.path.exists(args.recommendations_file):
        with open(args.recommendations_file, 'r') as f:
            recommendations = json.load(f)
    else:
        print("[WARNING] Recommendations file not found.")

    # Generate output path
    ad_account_id = metrics.get('ad_account_id', 'unknown').replace('act_', '')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(args.output_dir, f'facebook_ads_dashboard_{ad_account_id}_{timestamp}.html')

    create_facebook_html_dashboard(metrics, insights, recommendations, output_file)

    print(f"\nOpen in browser: {os.path.abspath(output_file)}")


if __name__ == '__main__':
    main()
