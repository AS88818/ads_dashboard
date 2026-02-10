#!/usr/bin/env python3
"""
Create an HTML dashboard with Google Ads insights and recommendations.
Alternative to Google Sheets when quota/access issues arise.
"""

import argparse
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from calculate_total_impact import aggregate_total_benefits

# Load environment variables
load_dotenv()

def create_html_dashboard(metrics, insights, recommendations, output_file):
    """Generate an HTML dashboard with insights and recommendations."""

    summary = metrics.get("summary", {})
    date_range = metrics.get("date_range", {})
    currency = os.getenv("CURRENCY", "MYR")
    currency_symbol = "RM" if currency == "MYR" else "$" if currency == "USD" else currency

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Google Ads Insights Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            color: #333;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1a73e8;
            border-bottom: 3px solid #1a73e8;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        h2 {{
            color: #1a73e8;
            margin-top: 30px;
            margin-bottom: 15px;
            border-left: 4px solid #1a73e8;
            padding-left: 15px;
        }}
        h3 {{
            color: #5f6368;
            margin-top: 20px;
            margin-bottom: 10px;
        }}
        .date-range {{
            background: #e8f0fe;
            padding: 10px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            color: #1967d2;
            font-weight: 500;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .metric-card.green {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        .metric-card.orange {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        .metric-card.blue {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }}
        .metric-label {{
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 32px;
            font-weight: bold;
        }}
        .insight-box {{
            background: #f8f9fa;
            border-left: 4px solid #34a853;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .issue-box {{
            background: #fef7e0;
            border-left: 4px solid #f9ab00;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .recommendation-card {{
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
            transition: all 0.3s;
        }}
        .recommendation-card:hover {{
            border-color: #1a73e8;
            box-shadow: 0 4px 12px rgba(26, 115, 232, 0.2);
        }}
        .rec-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .rec-type {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .type-bid {{ background: #e3f2fd; color: #1565c0; }}
        .type-keyword {{ background: #fff3e0; color: #e65100; }}
        .type-ad {{ background: #f3e5f5; color: #6a1b9a; }}
        .type-budget {{ background: #e8f5e9; color: #2e7d32; }}
        .rec-target {{
            font-size: 18px;
            font-weight: 600;
            color: #202124;
            margin-bottom: 10px;
        }}
        .rec-details {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 15px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        .detail-item {{
            display: flex;
            flex-direction: column;
        }}
        .detail-label {{
            font-size: 12px;
            color: #5f6368;
            margin-bottom: 5px;
        }}
        .detail-value {{
            font-size: 16px;
            font-weight: 600;
            color: #202124;
        }}
        .rec-reason {{
            background: white;
            padding: 15px;
            border-radius: 4px;
            color: #5f6368;
            line-height: 1.6;
        }}
        .rec-impact {{
            margin-top: 15px;
            padding: 12px;
            background: #e8f5e9;
            border-radius: 4px;
            color: #2e7d32;
            font-weight: 500;
        }}
        .checkbox {{
            width: 24px;
            height: 24px;
            cursor: pointer;
        }}
        ul {{
            margin-left: 20px;
            line-height: 1.8;
        }}
        .summary-text {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            line-height: 1.8;
            margin: 20px 0;
        }}
        .section-description {{
            background: #e8f0fe;
            padding: 15px 20px;
            border-radius: 6px;
            margin: 10px 0 20px 0;
            color: #1967d2;
            line-height: 1.6;
            border-left: 4px solid #1a73e8;
        }}
        .btn {{
            background: #1a73e8;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 4px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            margin: 20px 0;
        }}
        .btn:hover {{
            background: #1557b0;
        }}
        .note {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }}

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
            border-left: none;
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
            border-left: 3px solid #1a73e8;
            padding: 8px;
            margin-top: 8px;
            font-size: 12px;
            font-family: 'Courier New', monospace;
            color: #495057;
        }}

        @media print {{
            .btn {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Google Ads Performance Insights</h1>
        <div class="date-range">
            Period: {date_range.get('start_date', 'N/A')} to {date_range.get('end_date', 'N/A')} |
            Customer ID: {metrics.get('customer_id', 'N/A')}
        </div>

        <h2>📊 Key Metrics</h2>
        <div class="metrics-grid">
            <div class="metric-card blue">
                <div class="metric-label">Total Spend</div>
                <div class="metric-value">{currency_symbol} {summary.get('total_cost', 0):,.2f}</div>
            </div>
            <div class="metric-card green">
                <div class="metric-label">Conversions</div>
                <div class="metric-value">{summary.get('total_conversions', 0):.1f}</div>
            </div>
            <div class="metric-card orange">
                <div class="metric-label">Cost Per Conversion</div>
                <div class="metric-value">{currency_symbol} {summary.get('total_cost', 0) / summary.get('total_conversions', 1) if summary.get('total_conversions', 0) > 0 else 0:,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Clicks</div>
                <div class="metric-value">{summary.get('total_clicks', 0):,}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Impressions</div>
                <div class="metric-value">{summary.get('total_impressions', 0):,}</div>
            </div>
            <div class="metric-card green">
                <div class="metric-label">Average CTR</div>
                <div class="metric-value">{(summary.get('total_clicks', 0) / summary.get('total_impressions', 1) * 100) if summary.get('total_impressions', 0) > 0 else 0:.1f}%</div>
            </div>
        </div>

        <h2>💡 AI Insights Summary</h2>
        <div class="section-description">
            <strong>What this shows:</strong> Overall performance summary generated by AI analysis. This high-level overview helps you quickly understand your account's health, conversion efficiency, and total spend for the period.
        </div>
        <div class="summary-text">
            {insights.get('summary', 'No summary available')}
        </div>

        <h2>🏆 Top Performers</h2>
        <div class="section-description">
            <strong>What this shows:</strong> Your best-performing keywords, campaigns, and ads based on conversion rate and CPA (cost per acquisition). These are the winners you should scale up and use as templates for future campaigns.
        </div>
        <div>
"""

    for performer in insights.get('top_performers', []):
        html += f'            <div class="insight-box">✓ {performer}</div>\n'

    html += """
        </div>

        <h2>⚠️ Issues & Underperformers</h2>
        <div class="section-description">
            <strong>What this shows:</strong> Keywords, campaigns, or patterns that are wasting money or underperforming. These require immediate attention - either optimization, pausing, or strategic changes to improve ROI.
        </div>
        <div>
"""

    for issue in insights.get('underperformers', []):
        html += f'            <div class="issue-box">• {issue}</div>\n'

    html += f"""
        </div>
"""

    # Week 2 Quick Wins Section
    budget_pacing = insights.get('budget_pacing', {})
    landing_page_heatmap = insights.get('landing_page_heatmap', {})

    if budget_pacing:
        html += f"""
        <h2>💰 Budget Pacing Analysis</h2>
        <div class="section-description">
            <strong>What this shows:</strong> Your daily spend rate and projected monthly total. Alerts appear if you're spending too fast (budget may run out early) or too slow (leaving money on the table). Use this to adjust bids proactively and ensure optimal budget utilization.
        </div>
        <div class="metrics-grid">
            <div class="metric-card green">
                <div class="metric-label">Daily Avg Spend</div>
                <div class="metric-value">{currency_symbol} {budget_pacing.get('daily_avg_spend', 0):.2f}</div>
            </div>
            <div class="metric-card blue">
                <div class="metric-label">Projected Monthly</div>
                <div class="metric-value">{currency_symbol} {budget_pacing.get('projected_monthly_spend', 0):.2f}</div>
            </div>
            <div class="metric-card orange">
                <div class="metric-label">Days in Period</div>
                <div class="metric-value">{budget_pacing.get('days_in_period', 0)}</div>
            </div>
        </div>
"""

        if budget_pacing.get('alerts'):
            for alert in budget_pacing['alerts']:
                severity_class = 'issue-box' if alert['severity'] == 'HIGH' else 'insight-box'
                html += f"""
        <div class="{severity_class}">
            <strong>{alert['severity']}:</strong> {alert['message']}<br>
            <em>Recommendation: {alert['recommendation']}</em>
        </div>
"""

    if landing_page_heatmap and landing_page_heatmap.get('heatmap'):
        html += f"""
        <h2>🔥 Landing Page Performance Heatmap</h2>
        <div class="section-description">
            <strong>What this shows:</strong> Where your keywords are sending traffic and how well each landing page converts. High-traffic pages with low conversion rates are wasted opportunities. Sending many keywords to your homepage typically hurts Quality Score. Color-coded conversion rates show at a glance which pages need optimization.
        </div>
        <p>Total Landing Pages: {landing_page_heatmap.get('total_landing_pages', 0)}</p>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <thead style="background: #f0f0f0;">
                    <tr>
                        <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Landing Page</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Keywords</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Clicks</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Conv.</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Conv Rate</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Cost</th>
                    </tr>
                </thead>
                <tbody>
"""
        for page in landing_page_heatmap['heatmap'][:5]:
            conv_rate_color = '#22c55e' if page['conversion_rate'] > 5 else '#f59e0b' if page['conversion_rate'] > 2 else '#ef4444'
            html += f"""
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd; max-width: 300px; overflow: hidden; text-overflow: ellipsis;">{page['landing_page'][:60]}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{page['keywords_count']}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{page['clicks']}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{page['conversions']:.1f}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd; color: {conv_rate_color}; font-weight: bold;">{page['conversion_rate']:.1f}%</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{currency_symbol} {page['cost']:.2f}</td>
                    </tr>
"""

        html += """
                </tbody>
            </table>
        </div>
"""

        if landing_page_heatmap.get('issues'):
            html += "<h3>Landing Page Issues</h3>"
            for issue in landing_page_heatmap['issues']:
                html += f"""
        <div class="issue-box">
            <strong>{issue['severity']}: {issue['issue']}</strong><br>
            {issue['description']}<br>
            <em>Recommendation: {issue['recommendation']}</em>
        </div>
"""

    # Geographic Performance Section
    geo_performance = insights.get('geo_performance', {})
    if geo_performance and geo_performance.get('total_locations', 0) > 0:
        html += f"""
        <h2>🗺️ Geographic Performance Analysis</h2>
        <div class="section-description">
            <strong>What this shows:</strong> Where your ads are being shown and how each location performs. Identifies high-performing regions to scale and wasted spend in poor-converting locations. Use this to adjust location bids or exclude underperforming areas.
        </div>
        <p>Total Locations Analyzed: {geo_performance.get('total_locations', 0)}</p>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <thead style="background: #f0f0f0;">
                    <tr>
                        <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Location</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Impressions</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Clicks</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Conv.</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Conv Rate</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">CPA</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Cost</th>
                    </tr>
                </thead>
                <tbody>
"""
        for loc in geo_performance.get('locations', [])[:10]:
            # Color code by CPA
            cpa_color = '#22c55e' if loc.get('cost_per_conversion', 999) < 15 else '#f59e0b' if loc.get('cost_per_conversion', 999) < 25 else '#ef4444'
            html += f"""
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>{loc.get('location_name', 'Unknown')}</strong></td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{loc.get('impressions', 0):,}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{loc.get('clicks', 0):,}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{loc.get('conversions', 0):.0f}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{loc.get('conversion_rate', 0):.1f}%</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd; color: {cpa_color}; font-weight: bold;">{currency_symbol} {loc.get('cost_per_conversion', 0):.2f}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{currency_symbol} {loc.get('cost', 0):.2f}</td>
                    </tr>
"""

        html += """
                </tbody>
            </table>
        </div>
"""

        # Geo issues
        if geo_performance.get('issues'):
            html += "<h3>Geographic Issues</h3>"
            for issue in geo_performance['issues']:
                html += f"""
        <div class="issue-box">
            <strong>{issue['severity']}: {issue['issue']}</strong><br>
            {issue['description']}<br>
            <em>Recommendation: {issue['recommendation']}</em>
        </div>
"""

    # Time Performance Section
    time_performance = insights.get('time_performance', {})
    if time_performance and time_performance.get('hourly_performance'):
        html += f"""
        <h2>⏰ Time-of-Day & Day-of-Week Analysis</h2>
        <div class="section-description">
            <strong>What this shows:</strong> When your ads perform best by hour and day of week. Identifies wasted spend during low-performing time slots and opportunities to scale during peak hours. Use this to set ad schedules and bid adjustments by time.
        </div>
"""

        # Summary stats
        summary = time_performance.get('summary', {})
        if summary.get('best_hour'):
            html += f"""
        <p><strong>Best Hour:</strong> {summary['best_hour']} ({summary.get('best_hour_conv_rate', 0):.1f}% conversion rate)</p>
"""
        if summary.get('best_day'):
            html += f"""
        <p><strong>Best Day:</strong> {summary['best_day']} ({summary.get('best_day_conv_rate', 0):.1f}% conversion rate)</p>
"""

        # Hourly performance table (show top hours with activity)
        hourly_data = [h for h in time_performance.get('hourly_performance', []) if h.get('impressions', 0) > 0]
        if hourly_data:
            html += """
        <h3>Performance by Hour of Day</h3>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <thead style="background: #f0f0f0;">
                    <tr>
                        <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Hour</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Clicks</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Conv.</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Conv Rate</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Cost</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">CPA</th>
                    </tr>
                </thead>
                <tbody>
"""
            # Show hours with most activity (top 10 by cost)
            top_hours = sorted(hourly_data, key=lambda x: x.get('cost', 0), reverse=True)[:10]
            for h in top_hours:
                # Color code by conversion rate
                conv_rate = h.get('conversion_rate', 0)
                conv_color = '#22c55e' if conv_rate > 5 else '#f59e0b' if conv_rate > 2 else '#ef4444'
                cpa_display = f"{currency_symbol} {h.get('cost_per_conversion', 0):.2f}" if h.get('conversions', 0) > 0 else "-"

                html += f"""
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>{h.get('hour_label', '')}</strong></td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{h.get('clicks', 0):,}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{h.get('conversions', 0):.0f}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd; color: {conv_color}; font-weight: bold;">{conv_rate:.1f}%</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{currency_symbol} {h.get('cost', 0):.2f}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{cpa_display}</td>
                    </tr>
"""
            html += """
                </tbody>
            </table>
        </div>
"""

        # Daily performance table
        daily_data = time_performance.get('daily_performance', [])
        if daily_data and any(d.get('impressions', 0) > 0 for d in daily_data):
            html += """
        <h3>Performance by Day of Week</h3>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <thead style="background: #f0f0f0;">
                    <tr>
                        <th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Day</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Clicks</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Conv.</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Conv Rate</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">Cost</th>
                        <th style="padding: 10px; text-align: center; border: 1px solid #ddd;">CPA</th>
                    </tr>
                </thead>
                <tbody>
"""
            for d in daily_data:
                if d.get('impressions', 0) == 0:
                    continue
                conv_rate = d.get('conversion_rate', 0)
                conv_color = '#22c55e' if conv_rate > 5 else '#f59e0b' if conv_rate > 2 else '#ef4444'
                cpa_display = f"{currency_symbol} {d.get('cost_per_conversion', 0):.2f}" if d.get('conversions', 0) > 0 else "-"

                html += f"""
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>{d.get('day', '')}</strong></td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{d.get('clicks', 0):,}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{d.get('conversions', 0):.0f}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd; color: {conv_color}; font-weight: bold;">{conv_rate:.1f}%</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{currency_symbol} {d.get('cost', 0):.2f}</td>
                        <td style="padding: 10px; text-align: center; border: 1px solid #ddd;">{cpa_display}</td>
                    </tr>
"""
            html += """
                </tbody>
            </table>
        </div>
"""

        # Time issues
        if time_performance.get('issues'):
            html += "<h3>Time-Based Issues</h3>"
            for issue in time_performance['issues']:
                html += f"""
        <div class="issue-box">
            <strong>{issue['severity']}: {issue['issue']}</strong><br>
            {issue['description']}<br>
            <em>Recommendation: {issue['recommendation']}</em>
        </div>
"""

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
                    <div class="metric-label">Monthly Savings</div>
                    <div class="metric-value">{currency_symbol} {totals['total_monthly_savings']:,.0f}</div>
                    <div class="metric-label" style="margin-top: 10px; font-size: 12px;">From eliminating waste</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Additional Conversions</div>
                    <div class="metric-value">{totals['total_additional_conversions']:.0f}</div>
                    <div class="metric-label" style="margin-top: 10px; font-size: 12px;">Monthly projection</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Additional Revenue</div>
                    <div class="metric-value">{currency_symbol} {totals['total_additional_revenue']:,.0f}</div>
                    <div class="metric-label" style="margin-top: 10px; font-size: 12px;">From scaling winners</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Net Monthly Benefit</div>
                    <div class="metric-value">{currency_symbol} {totals['total_net_benefit']:,.0f}</div>
                    <div class="metric-label" style="margin-top: 10px; font-size: 12px;">Total value unlock</div>
                </div>
            </div>
            <p style="margin-top: 20px; font-size: 13px; opacity: 0.85;">
                <strong>Automation Status:</strong> {totals['automatable_count']} auto-actionable, {totals['manual_count']} manual required
            </p>
        </div>

        <h2>🎯 Optimization Recommendations ({len(recommendations)} total)</h2>
        <div class="section-description">
            <strong>What this shows:</strong> AI-generated action items prioritized by potential impact. Each recommendation includes current vs. suggested values, reasoning, and expected outcomes. These are ranked from highest to lowest impact—tackle them in order for maximum ROI improvement.
        </div>
        <div class="note">
            <strong>Note:</strong> Review each recommendation below. To apply these changes, inform your account manager or use the
            <code>apply_google_ads_changes.py</code> script with the JSON file.
        </div>
"""

    for i, rec in enumerate(recommendations, 1):
        rec_type = rec.get('type', 'unknown')
        type_class = 'bid' if 'bid' in rec_type else 'keyword' if 'keyword' in rec_type else 'ad' if 'ad' in rec_type else 'budget'

        # Determine target display based on type
        if rec_type == 'schedule_bid_adjustment':
            target_display = rec.get('time_slot', 'N/A')
        elif rec_type in ['geo_exclusion', 'geo_bid_adjustment']:
            target_display = rec.get('location', 'N/A')
        else:
            target_display = rec.get('keyword', rec.get('target', 'N/A'))

        # Get automation and impact metadata
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
        <div class="recommendation-card">
            <div class="rec-header">
                <div>
                    <span class="rec-type type-{type_class}">{rec_type.replace('_', ' ')}</span>
                    <span class="automation-badge {auto_class}">{auto_badge}</span>
                    <span class="confidence-badge {confidence_class}">{confidence_pct}%</span>
                    <div class="rec-target">{i}. {target_display}</div>
                </div>
            </div>
"""

        # Add details based on type
        if rec_type == 'bid_adjustment':
            html += f"""
            <div class="rec-details">
                <div class="detail-item">
                    <div class="detail-label">Current Bid</div>
                    <div class="detail-value">{currency_symbol} {rec.get('current_bid', 0):.2f}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Suggested Bid</div>
                    <div class="detail-value">{currency_symbol} {rec.get('suggested_bid', 0):.2f}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Change</div>
                    <div class="detail-value">{((rec.get('suggested_bid', 0) - rec.get('current_bid', 0)) / rec.get('current_bid', 1) * 100) if rec.get('current_bid', 0) > 0 else 0:+.1f}%</div>
                </div>
            </div>
"""
        elif rec_type == 'keyword_action':
            html += f"""
            <div class="rec-details">
                <div class="detail-item">
                    <div class="detail-label">Action</div>
                    <div class="detail-value">{rec.get('action', 'N/A').replace('_', ' ').title()}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Current</div>
                    <div class="detail-value">{rec.get('current', 'N/A')}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Suggested Fix</div>
                    <div class="detail-value" style="font-weight: bold; color: #059669;">{rec.get('suggested', 'N/A')}</div>
                </div>
"""
            # Add negative keywords list if present
            if rec.get('negative_keywords') and len(rec.get('negative_keywords', [])) > 0:
                html += f"""
                <div class="detail-item" style="grid-column: span 3;">
                    <div class="detail-label">Negative Keywords to Add</div>
                    <div class="detail-value" style="background: #fef3c7; padding: 8px; border-radius: 4px;">
                        {', '.join([f'<strong>-{nk}</strong>' for nk in rec.get('negative_keywords', [])])}
                    </div>
                </div>
"""
            # Add how-to-apply if present
            if rec.get('how_to_apply'):
                html += f"""
                <div class="detail-item" style="grid-column: span 3;">
                    <div class="detail-label">How to Apply</div>
                    <div class="detail-value" style="background: #e0f2fe; padding: 8px; border-radius: 4px; font-style: italic;">
                        {rec.get('how_to_apply')}
                    </div>
                </div>
"""
            html += """
            </div>
"""
        elif rec_type == 'ad_copy':
            image_prompt = rec.get('image_prompt', '')
            html += f"""
            <div class="rec-details">
                <div class="detail-item">
                    <div class="detail-label">Ad Group</div>
                    <div class="detail-value">{rec.get('ad_group_name', 'N/A')}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Headline</div>
                    <div class="detail-value">{rec.get('headline', 'N/A')}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Description</div>
                    <div class="detail-value">{rec.get('description', 'N/A')}</div>
                </div>
            </div>
"""
            if image_prompt:
                html += f"""
            <div class="rec-image-prompt">
                <strong>🎨 AI Image Prompt:</strong>
                <div style="background: #f8f9fa; padding: 12px; margin-top: 8px; border-radius: 4px; font-size: 14px; line-height: 1.6; font-style: italic; color: #555;">
                    {image_prompt}
                </div>
                <div style="margin-top: 8px; font-size: 12px; color: #666;">
                    💡 Use this prompt with DALL-E, Midjourney, or Stable Diffusion to generate ad images
                </div>
            </div>
"""
        elif rec_type == 'quality_improvement':
            html += f"""
            <div class="rec-details">
                <div class="detail-item">
                    <div class="detail-label">Issue</div>
                    <div class="detail-value">{rec.get('issue', 'N/A')}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Action Required</div>
                    <div class="detail-value">{rec.get('suggested', 'N/A')}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Affected</div>
                    <div class="detail-value">{rec.get('target', 'N/A')}</div>
                </div>
            </div>
"""
        elif rec_type == 'schedule_bid_adjustment':
            html += f"""
            <div class="rec-details">
                <div class="detail-item">
                    <div class="detail-label">Time Slot</div>
                    <div class="detail-value">{rec.get('time_slot', 'N/A')}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Current Spend</div>
                    <div class="detail-value">{currency_symbol} {rec.get('current_spend', 0):.2f}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Suggested Adjustment</div>
                    <div class="detail-value">{rec.get('suggested_adjustment', 'N/A')}</div>
                </div>
"""
            # Add current performance if available
            if rec.get('current_performance'):
                html += f"""
                <div class="detail-item">
                    <div class="detail-label">Current Performance</div>
                    <div class="detail-value">{rec.get('current_performance')}</div>
                </div>
"""
            html += """
            </div>
"""
        elif rec_type == 'geo_exclusion':
            html += f"""
            <div class="rec-details">
                <div class="detail-item">
                    <div class="detail-label">Location</div>
                    <div class="detail-value">{rec.get('location', 'N/A')}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Action</div>
                    <div class="detail-value">EXCLUDE</div>
                </div>
            </div>
"""
        elif rec_type == 'geo_bid_adjustment':
            html += f"""
            <div class="rec-details">
                <div class="detail-item">
                    <div class="detail-label">Location</div>
                    <div class="detail-value">{rec.get('location', 'N/A')}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Current CPA</div>
                    <div class="detail-value">{currency_symbol} {rec.get('current_cpa', 0):.2f}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Suggested Adjustment</div>
                    <div class="detail-value">{rec.get('suggested_adjustment', 'N/A')}</div>
                </div>
            </div>
"""

        html += f"""
            <div class="rec-reason">
                <strong>Reason:</strong> {rec.get('reason', 'No reason provided')}
            </div>
            <div class="rec-impact">
                <strong>Expected Impact:</strong> {rec.get('expected_impact', 'TBD')}
            </div>
"""

        # Add formula explanation if available
        if formula:
            html += f"""
            <div class="formula-explain">
                <span style="margin-right: 5px;">📊</span>{formula}
            </div>
"""

        # Add manual explanation if needed
        if manual_reason:
            html += f"""
            <div class="manual-explanation">
                <strong>Why Manual?</strong> {manual_reason}
            </div>
"""

        html += """
        </div>
"""

    html += f"""
        <h2>📁 Data Files</h2>
        <p>All analysis data has been saved to:</p>
        <ul>
            <li><strong>Metrics:</strong> .tmp/google_ads_metrics_{metrics.get('customer_id', '')}_*.json</li>
            <li><strong>Insights:</strong> .tmp/insights_{metrics.get('customer_id', '')}.json</li>
            <li><strong>Recommendations:</strong> .tmp/recommendations_{metrics.get('customer_id', '')}.json</li>
        </ul>

        <div class="note">
            <strong>Next Steps:</strong>
            <ol style="margin-left: 20px; margin-top: 10px;">
                <li>Review all recommendations carefully</li>
                <li>Decide which changes to implement</li>
                <li>Tell Claude "apply these recommendations: [list numbers]" to execute</li>
                <li>Monitor performance after changes are applied</li>
            </ol>
        </div>

        <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 2px solid #e0e0e0; color: #5f6368;">
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} by Claude Code Agentic Workflow</p>
        </div>
    </div>

    <script>
        // Add print functionality
        function printDashboard() {{
            window.print();
        }}

        // Add copy functionality for recommendations
        document.querySelectorAll('.recommendation-card').forEach((card, index) => {{
            card.style.cursor = 'pointer';
            card.title = 'Click for details';
        }});
    </script>
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_file


def main():
    parser = argparse.ArgumentParser(description="Create HTML insights dashboard")
    parser.add_argument("--metrics_file", required=True, help="Path to metrics JSON file")
    parser.add_argument("--insights_file", required=True, help="Path to insights JSON file")
    parser.add_argument("--recommendations_file", required=True, help="Path to recommendations JSON file")
    parser.add_argument("--output_file", default=None, help="Output HTML file path")

    args = parser.parse_args()

    # Load data files
    print("Loading data files...")
    with open(args.metrics_file, 'r') as f:
        metrics = json.load(f)

    with open(args.insights_file, 'r') as f:
        insights = json.load(f)

    with open(args.recommendations_file, 'r') as f:
        recommendations = json.load(f)

    # Generate output filename if not provided
    if not args.output_file:
        customer_id = metrics.get('customer_id', 'unknown')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.output_file = f".tmp/google_ads_dashboard_{customer_id}_{timestamp}.html"

    print(f"Creating HTML dashboard: {args.output_file}")
    output_path = create_html_dashboard(metrics, insights, recommendations, args.output_file)

    print()
    print("="*70)
    print("SUCCESS!")
    print("="*70)
    print()
    print(f"Dashboard created: {output_path}")
    print()
    print("To view:")
    print(f"  1. Open the file in your browser")
    print(f"  2. Or run: start {output_path}")
    print()


if __name__ == "__main__":
    main()
