#!/usr/bin/env python3
"""
Fetch comprehensive Facebook/Meta Ads metrics.

Retrieves campaign, ad set, ad, demographic, placement, geographic,
and time performance data from the Meta Marketing API.

Usage:
    python execution/fetch_facebook_ads_metrics.py \
        --ad_account_id act_XXXXXXXXX \
        --start_date 2025-01-01 \
        --end_date 2025-01-31

    # Or use defaults from .env:
    python execution/fetch_facebook_ads_metrics.py --days 30
"""

import json
import argparse
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Import Facebook Business SDK
try:
    from facebook_business.api import FacebookAdsApi
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.campaign import Campaign
    from facebook_business.adobjects.adset import AdSet
    from facebook_business.adobjects.ad import Ad
    from facebook_business.adobjects.adcreative import AdCreative
except ImportError:
    print("[ERROR] facebook-business package not installed.")
    print("  Run: pip install facebook-business==20.0.0")
    sys.exit(1)


def init_facebook_api():
    """Initialize the Facebook Ads API from environment variables."""
    app_id = os.getenv('FACEBOOK_APP_ID')
    app_secret = os.getenv('FACEBOOK_APP_SECRET')
    access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')

    if not access_token:
        print("[ERROR] FACEBOOK_ACCESS_TOKEN not set in .env")
        sys.exit(1)

    FacebookAdsApi.init(app_id or '', app_secret or '', access_token)
    print("[OK] Facebook Ads API initialized")


def parse_actions(actions_list, action_type='lead'):
    """
    Parse Facebook's actions array to extract conversions.

    Facebook returns actions as:
    [{"action_type": "lead", "value": "5"}, {"action_type": "link_click", "value": "100"}]

    Common action types: lead, purchase, complete_registration, add_to_cart,
    initiate_checkout, search, view_content, contact, schedule, submit_application,
    Messenger/WhatsApp conversions: onsite_conversion.total_messaging_connection,
    onsite_conversion.messaging_first_reply
    """
    if not actions_list:
        return 0

    total = 0
    for action in actions_list:
        atype = action.get('action_type', '')
        # Count leads, purchases, and other conversion actions (including Messenger/WhatsApp)
        if atype in (action_type, 'lead', 'purchase', 'complete_registration',
                     'contact', 'schedule', 'submit_application',
                     'onsite_conversion.messaging_conversation_started_7d',
                     'onsite_conversion.total_messaging_connection',
                     'onsite_conversion.messaging_first_reply',
                     'onsite_conversion.messaging_block',
                     'onsite_conversion.messaging_user_depth_2_message_send',
                     'offsite_conversion.fb_pixel_lead'):
            total += int(action.get('value', 0))
    return total


def parse_cost_per_action(cost_per_action_list, action_type='lead'):
    """Parse Facebook's cost_per_action_type to get CPA."""
    if not cost_per_action_list:
        return 0

    for action in cost_per_action_list:
        if action.get('action_type') == action_type:
            return float(action.get('value', 0))

    # Fallback: try lead, then any conversion action
    for action in cost_per_action_list:
        if action.get('action_type') in ('lead', 'purchase', 'complete_registration', 'contact'):
            return float(action.get('value', 0))

    return 0


def parse_action_values(action_values_list):
    """Parse conversion values from action_values."""
    if not action_values_list:
        return 0

    total = 0
    for av in action_values_list:
        if av.get('action_type') in ('lead', 'purchase', 'complete_registration',
                                      'offsite_conversion.fb_pixel_purchase'):
            total += float(av.get('value', 0))
    return total


def fetch_campaign_metrics(account, start_date, end_date):
    """Fetch campaign-level performance metrics."""
    print("  Fetching campaign metrics...")

    fields = [
        'campaign_name', 'campaign_id', 'objective',
        'impressions', 'reach', 'frequency',
        'clicks', 'unique_clicks', 'ctr', 'unique_ctr',
        'cpc', 'cpm', 'cpp', 'spend',
        'actions', 'action_values', 'cost_per_action_type',
    ]

    params = {
        'time_range': {'since': start_date, 'until': end_date},
        'level': 'campaign',
        'filtering': [{'field': 'campaign.delivery_info', 'operator': 'IN', 'value': ['active', 'inactive', 'completed', 'not_delivering', 'limited']}],
    }

    try:
        insights = account.get_insights(fields=fields, params=params)
    except Exception as e:
        # If delivery_info filter fails, try without it
        print(f"    Retrying without delivery filter: {e}")
        params.pop('filtering', None)
        insights = account.get_insights(fields=fields, params=params)

    campaigns = []
    for row in insights:
        conversions = parse_actions(row.get('actions'))
        conversion_value = parse_action_values(row.get('action_values'))
        cpa = parse_cost_per_action(row.get('cost_per_action_type'))
        spend = float(row.get('spend', 0))

        campaigns.append({
            'campaign_name': row.get('campaign_name', 'Unknown'),
            'campaign_id': row.get('campaign_id', ''),
            'objective': row.get('objective', ''),
            'impressions': int(row.get('impressions', 0)),
            'reach': int(row.get('reach', 0)),
            'frequency': float(row.get('frequency', 0)),
            'clicks': int(row.get('clicks', 0)),
            'unique_clicks': int(row.get('unique_clicks', 0)),
            'ctr': float(row.get('ctr', 0)),
            'unique_ctr': float(row.get('unique_ctr', 0)),
            'cpc': float(row.get('cpc', 0)),
            'cpm': float(row.get('cpm', 0)),
            'spend': spend,
            'conversions': conversions,
            'conversion_value': conversion_value,
            'cost_per_conversion': cpa if cpa > 0 else (spend / conversions if conversions > 0 else 0),
            'roas': conversion_value / spend if spend > 0 else 0,
        })

    # Also fetch campaign status
    campaign_statuses = {}
    try:
        campaigns_obj = account.get_campaigns(
            fields=['name', 'status', 'effective_status', 'daily_budget', 'lifetime_budget'],
        )
        for c in campaigns_obj:
            campaign_statuses[c.get('id', '')] = {
                'status': c.get('effective_status', c.get('status', 'UNKNOWN')),
                'daily_budget': float(c.get('daily_budget', 0)) / 100 if c.get('daily_budget') else 0,
                'lifetime_budget': float(c.get('lifetime_budget', 0)) / 100 if c.get('lifetime_budget') else 0,
            }
    except Exception as e:
        print(f"    Warning: Could not fetch campaign statuses: {e}")

    # Merge status into metrics
    for camp in campaigns:
        status_info = campaign_statuses.get(camp['campaign_id'], {})
        camp['status'] = status_info.get('status', 'UNKNOWN')
        camp['daily_budget'] = status_info.get('daily_budget', 0)
        camp['lifetime_budget'] = status_info.get('lifetime_budget', 0)

    print(f"    Found {len(campaigns)} campaigns")
    return campaigns


def fetch_campaign_daily_metrics(account, start_date, end_date):
    """Fetch campaign-level metrics segmented by date for fast dashboard filtering."""
    print("  Fetching daily campaign metrics...")

    fields = [
        'campaign_name', 'campaign_id', 'objective',
        'impressions', 'reach', 'frequency',
        'clicks', 'unique_clicks', 'ctr', 'unique_ctr',
        'cpc', 'cpm', 'cpp', 'spend',
        'actions', 'action_values', 'cost_per_action_type',
        'date_start', 'date_stop',
    ]

    params = {
        'time_range': {'since': start_date, 'until': end_date},
        'level': 'campaign',
        'time_increment': 1,
    }

    insights = account.get_insights(fields=fields, params=params)

    rows = []
    for row in insights:
        conversions = parse_actions(row.get('actions'))
        conversion_value = parse_action_values(row.get('action_values'))
        cpa = parse_cost_per_action(row.get('cost_per_action_type'))
        spend = float(row.get('spend', 0))

        rows.append({
            'date': row.get('date_start'),
            'campaign_name': row.get('campaign_name', 'Unknown'),
            'campaign_id': row.get('campaign_id', ''),
            'objective': row.get('objective', ''),
            'impressions': int(row.get('impressions', 0)),
            'reach': int(row.get('reach', 0)),
            'frequency': float(row.get('frequency', 0)),
            'clicks': int(row.get('clicks', 0)),
            'unique_clicks': int(row.get('unique_clicks', 0)),
            'ctr': float(row.get('ctr', 0)),
            'unique_ctr': float(row.get('unique_ctr', 0)),
            'cpc': float(row.get('cpc', 0)),
            'cpm': float(row.get('cpm', 0)),
            'spend': spend,
            'conversions': conversions,
            'conversion_value': conversion_value,
            'cost_per_conversion': cpa if cpa > 0 else (spend / conversions if conversions > 0 else 0),
            'roas': conversion_value / spend if spend > 0 else 0,
        })

    print(f"    Found {len(rows)} daily campaign rows")
    return rows


def fetch_adset_metrics(account, start_date, end_date):
    """Fetch ad set-level performance metrics."""
    print("  Fetching ad set metrics...")

    fields = [
        'adset_name', 'adset_id', 'campaign_name', 'campaign_id',
        'impressions', 'reach', 'frequency',
        'clicks', 'ctr', 'cpc', 'cpm', 'spend',
        'actions', 'action_values', 'cost_per_action_type',
    ]

    params = {
        'time_range': {'since': start_date, 'until': end_date},
        'level': 'adset',
    }

    insights = account.get_insights(fields=fields, params=params)

    # Also fetch targeting info
    adset_targeting = {}
    try:
        adsets = account.get_ad_sets(
            fields=['name', 'targeting', 'optimization_goal', 'billing_event',
                    'daily_budget', 'lifetime_budget', 'status', 'effective_status'],
        )
        for adset in adsets:
            targeting = adset.get('targeting', {})
            # Summarize targeting
            targeting_summary = _summarize_targeting(targeting)
            adset_targeting[adset.get('id', '')] = {
                'targeting_summary': targeting_summary,
                'optimization_goal': adset.get('optimization_goal', ''),
                'billing_event': adset.get('billing_event', ''),
                'daily_budget': float(adset.get('daily_budget', 0)) / 100 if adset.get('daily_budget') else 0,
                'lifetime_budget': float(adset.get('lifetime_budget', 0)) / 100 if adset.get('lifetime_budget') else 0,
                'status': adset.get('effective_status', adset.get('status', 'UNKNOWN')),
            }
    except Exception as e:
        print(f"    Warning: Could not fetch ad set details: {e}")

    ad_sets = []
    for row in insights:
        conversions = parse_actions(row.get('actions'))
        spend = float(row.get('spend', 0))
        adset_id = row.get('adset_id', '')
        extra = adset_targeting.get(adset_id, {})

        ad_sets.append({
            'adset_name': row.get('adset_name', 'Unknown'),
            'adset_id': adset_id,
            'campaign_name': row.get('campaign_name', ''),
            'campaign_id': row.get('campaign_id', ''),
            'status': extra.get('status', 'UNKNOWN'),
            'optimization_goal': extra.get('optimization_goal', ''),
            'targeting_summary': extra.get('targeting_summary', ''),
            'daily_budget': extra.get('daily_budget', 0),
            'lifetime_budget': extra.get('lifetime_budget', 0),
            'impressions': int(row.get('impressions', 0)),
            'reach': int(row.get('reach', 0)),
            'frequency': float(row.get('frequency', 0)),
            'clicks': int(row.get('clicks', 0)),
            'ctr': float(row.get('ctr', 0)),
            'cpc': float(row.get('cpc', 0)),
            'cpm': float(row.get('cpm', 0)),
            'spend': spend,
            'conversions': conversions,
            'cost_per_conversion': spend / conversions if conversions > 0 else 0,
        })

    print(f"    Found {len(ad_sets)} ad sets")
    return ad_sets


def _summarize_targeting(targeting):
    """Create a human-readable summary of ad set targeting."""
    parts = []

    # Age/Gender
    age_min = targeting.get('age_min', '')
    age_max = targeting.get('age_max', '')
    if age_min or age_max:
        parts.append(f"Age {age_min}-{age_max}")

    genders = targeting.get('genders', [])
    gender_map = {1: 'Male', 2: 'Female'}
    if genders:
        parts.append('/'.join(gender_map.get(g, str(g)) for g in genders))

    # Locations
    geo = targeting.get('geo_locations', {})
    countries = geo.get('countries', [])
    cities = geo.get('cities', [])
    regions = geo.get('regions', [])

    if countries:
        parts.append(f"Countries: {', '.join(countries)}")
    if cities:
        city_names = [c.get('name', c.get('key', '')) for c in cities[:3]]
        parts.append(f"Cities: {', '.join(city_names)}")
    if regions:
        region_names = [r.get('name', r.get('key', '')) for r in regions[:3]]
        parts.append(f"Regions: {', '.join(region_names)}")

    # Interests
    interests = targeting.get('flexible_spec', [])
    if interests:
        interest_names = []
        for spec in interests:
            for interest in spec.get('interests', []):
                interest_names.append(interest.get('name', ''))
            for behavior in spec.get('behaviors', []):
                interest_names.append(behavior.get('name', ''))
        if interest_names:
            parts.append(f"Interests: {', '.join(interest_names[:5])}")

    # Custom audiences
    custom_audiences = targeting.get('custom_audiences', [])
    if custom_audiences:
        parts.append(f"{len(custom_audiences)} custom audience(s)")

    return ' | '.join(parts) if parts else 'Broad targeting'


def fetch_ad_metrics(account, start_date, end_date):
    """Fetch ad-level performance metrics with creative details."""
    print("  Fetching ad metrics...")

    fields = [
        'ad_name', 'ad_id', 'adset_name', 'adset_id',
        'campaign_name', 'campaign_id',
        'impressions', 'reach', 'frequency',
        'clicks', 'ctr', 'cpc', 'cpm', 'spend',
        'actions', 'cost_per_action_type',
    ]

    params = {
        'time_range': {'since': start_date, 'until': end_date},
        'level': 'ad',
        'limit': 500,
    }

    insights = account.get_insights(fields=fields, params=params)

    # Fetch creative details
    ad_creatives = {}
    try:
        ads_list = account.get_ads(
            fields=['name', 'creative', 'status', 'effective_status'],
        )
        for ad in ads_list:
            creative_ref = ad.get('creative', {})
            ad_id = ad.get('id', '')
            ad_creatives[ad_id] = {
                'creative_id': creative_ref.get('id', ''),
                'status': ad.get('effective_status', ad.get('status', 'UNKNOWN')),
            }

            # Try to fetch creative details
            if creative_ref.get('id'):
                try:
                    creative = AdCreative(creative_ref['id']).api_get(
                        fields=['title', 'body', 'link_url', 'call_to_action_type',
                                'image_url', 'thumbnail_url', 'object_story_spec']
                    )
                    ad_creatives[ad_id].update({
                        'headline': creative.get('title', ''),
                        'body': creative.get('body', ''),
                        'link_url': creative.get('link_url', ''),
                        'cta': creative.get('call_to_action_type', ''),
                        'image_url': creative.get('image_url') or creative.get('thumbnail_url', ''),
                    })

                    # Try to extract from object_story_spec
                    oss = creative.get('object_story_spec', {})
                    link_data = oss.get('link_data', {})
                    if link_data:
                        if not ad_creatives[ad_id]['headline']:
                            ad_creatives[ad_id]['headline'] = link_data.get('name', '')
                        if not ad_creatives[ad_id]['body']:
                            ad_creatives[ad_id]['body'] = link_data.get('message', '')
                        if not ad_creatives[ad_id]['link_url']:
                            ad_creatives[ad_id]['link_url'] = link_data.get('link', '')

                except Exception:
                    pass  # Creative details are nice-to-have, not essential

    except Exception as e:
        print(f"    Warning: Could not fetch ad creatives: {e}")

    ads = []
    for row in insights:
        conversions = parse_actions(row.get('actions'))
        spend = float(row.get('spend', 0))
        ad_id = row.get('ad_id', '')
        creative_info = ad_creatives.get(ad_id, {})

        ads.append({
            'ad_name': row.get('ad_name', 'Unknown'),
            'ad_id': ad_id,
            'adset_name': row.get('adset_name', ''),
            'campaign_name': row.get('campaign_name', ''),
            'status': creative_info.get('status', 'UNKNOWN'),
            'headline': creative_info.get('headline', ''),
            'body': creative_info.get('body', ''),
            'link_url': creative_info.get('link_url', ''),
            'cta': creative_info.get('cta', ''),
            'impressions': int(row.get('impressions', 0)),
            'reach': int(row.get('reach', 0)),
            'frequency': float(row.get('frequency', 0)),
            'clicks': int(row.get('clicks', 0)),
            'ctr': float(row.get('ctr', 0)),
            'cpc': float(row.get('cpc', 0)),
            'cpm': float(row.get('cpm', 0)),
            'spend': spend,
            'conversions': conversions,
            'cost_per_conversion': spend / conversions if conversions > 0 else 0,
        })

    print(f"    Found {len(ads)} ads")
    return ads


def fetch_demographic_breakdown(account, start_date, end_date):
    """Fetch age × gender performance breakdown."""
    print("  Fetching demographic breakdown...")

    fields = [
        'impressions', 'reach', 'clicks', 'spend',
        'actions', 'ctr', 'cpc',
    ]

    params = {
        'time_range': {'since': start_date, 'until': end_date},
        'breakdowns': ['age', 'gender'],
    }

    insights = account.get_insights(fields=fields, params=params)

    demographics = []
    for row in insights:
        conversions = parse_actions(row.get('actions'))
        spend = float(row.get('spend', 0))

        demographics.append({
            'age': row.get('age', ''),
            'gender': row.get('gender', ''),
            'impressions': int(row.get('impressions', 0)),
            'reach': int(row.get('reach', 0)),
            'clicks': int(row.get('clicks', 0)),
            'ctr': float(row.get('ctr', 0)),
            'cpc': float(row.get('cpc', 0)),
            'spend': spend,
            'conversions': conversions,
            'cost_per_conversion': spend / conversions if conversions > 0 else 0,
        })

    print(f"    Found {len(demographics)} demographic segments")
    return demographics


def fetch_placement_breakdown(account, start_date, end_date):
    """Fetch placement performance breakdown (feed, stories, reels, etc.)."""
    print("  Fetching placement breakdown...")

    fields = [
        'impressions', 'reach', 'clicks', 'spend',
        'actions', 'ctr', 'cpc', 'cpm',
    ]

    params = {
        'time_range': {'since': start_date, 'until': end_date},
        'breakdowns': ['publisher_platform', 'platform_position'],
    }

    insights = account.get_insights(fields=fields, params=params)

    placements = []
    for row in insights:
        conversions = parse_actions(row.get('actions'))
        spend = float(row.get('spend', 0))

        platform = row.get('publisher_platform', '')
        position = row.get('platform_position', '')
        # Create readable name
        placement_name = f"{platform} - {position}".replace('_', ' ').title()

        placements.append({
            'platform': platform,
            'position': position,
            'placement_name': placement_name,
            'impressions': int(row.get('impressions', 0)),
            'reach': int(row.get('reach', 0)),
            'clicks': int(row.get('clicks', 0)),
            'ctr': float(row.get('ctr', 0)),
            'cpc': float(row.get('cpc', 0)),
            'cpm': float(row.get('cpm', 0)),
            'spend': spend,
            'conversions': conversions,
            'cost_per_conversion': spend / conversions if conversions > 0 else 0,
        })

    print(f"    Found {len(placements)} placement segments")
    return placements


def fetch_geographic_breakdown(account, start_date, end_date):
    """Fetch geographic performance breakdown."""
    print("  Fetching geographic breakdown...")

    fields = [
        'impressions', 'reach', 'clicks', 'spend',
        'actions', 'action_values', 'cost_per_action_type',
        'ctr', 'cpc',
    ]

    params = {
        'time_range': {'since': start_date, 'until': end_date},
        'breakdowns': ['country', 'region'],
        'action_attribution_windows': ['7d_click', '1d_view'],
    }

    insights = account.get_insights(fields=fields, params=params)

    geo_data = []
    for row in insights:
        conversions = parse_actions(row.get('actions'))
        spend = float(row.get('spend', 0))

        geo_data.append({
            'country': row.get('country', ''),
            'region': row.get('region', ''),
            'location_name': f"{row.get('region', '')}, {row.get('country', '')}".strip(', '),
            'impressions': int(row.get('impressions', 0)),
            'reach': int(row.get('reach', 0)),
            'clicks': int(row.get('clicks', 0)),
            'ctr': float(row.get('ctr', 0)),
            'cpc': float(row.get('cpc', 0)),
            'spend': spend,
            'conversions': conversions,
            'cost_per_conversion': spend / conversions if conversions > 0 else 0,
        })

    print(f"    Found {len(geo_data)} geographic segments")
    return geo_data


def fetch_time_breakdown(account, start_date, end_date):
    """Fetch daily and hourly performance breakdown."""
    print("  Fetching time breakdown...")

    fields = [
        'impressions', 'clicks', 'spend', 'actions', 'ctr',
    ]

    # Daily breakdown
    daily_params = {
        'time_range': {'since': start_date, 'until': end_date},
        'time_increment': 1,
        'action_attribution_windows': ['7d_click', '1d_view'],
    }

    daily_insights = account.get_insights(fields=fields, params=daily_params)

    daily_data = []
    for row in daily_insights:
        conversions = parse_actions(row.get('actions'))
        spend = float(row.get('spend', 0))

        daily_data.append({
            'date': row.get('date_start', ''),
            'impressions': int(row.get('impressions', 0)),
            'clicks': int(row.get('clicks', 0)),
            'ctr': float(row.get('ctr', 0)),
            'spend': spend,
            'conversions': conversions,
        })

    # Hourly breakdown
    hourly_params = {
        'time_range': {'since': start_date, 'until': end_date},
        'breakdowns': ['hourly_stats_aggregated_by_advertiser_time_zone'],
        'action_attribution_windows': ['7d_click', '1d_view'],
    }

    hourly_data = []
    try:
        hourly_insights = account.get_insights(fields=fields, params=hourly_params)

        for row in hourly_insights:
            conversions = parse_actions(row.get('actions'))
            spend = float(row.get('spend', 0))
            hour_range = row.get('hourly_stats_aggregated_by_advertiser_time_zone', '')

            # Parse hour from format like "00:00:00 - 00:59:59"
            hour = 0
            if hour_range and ':' in hour_range:
                try:
                    hour = int(hour_range.split(':')[0])
                except (ValueError, IndexError):
                    pass

            hourly_data.append({
                'hour': hour,
                'hour_range': hour_range,
                'impressions': int(row.get('impressions', 0)),
                'clicks': int(row.get('clicks', 0)),
                'ctr': float(row.get('ctr', 0)),
                'spend': spend,
                'conversions': conversions,
            })
    except Exception as e:
        print(f"    Warning: Could not fetch hourly data: {e}")

    print(f"    Found {len(daily_data)} daily records, {len(hourly_data)} hourly records")
    return {'daily': daily_data, 'hourly': hourly_data}


def build_summary(campaigns, ad_sets, ads):
    """Build summary metrics from all data."""
    total_spend = sum(c['spend'] for c in campaigns)
    total_impressions = sum(c['impressions'] for c in campaigns)
    total_reach = sum(c['reach'] for c in campaigns)
    total_clicks = sum(c['clicks'] for c in campaigns)
    total_conversions = sum(c['conversions'] for c in campaigns)
    total_conversion_value = sum(c.get('conversion_value', 0) for c in campaigns)

    return {
        'total_campaigns': len(campaigns),
        'total_ad_sets': len(ad_sets),
        'total_ads': len(ads),
        'total_impressions': total_impressions,
        'total_reach': total_reach,
        'total_frequency': round(total_impressions / total_reach, 2) if total_reach > 0 else 0,
        'total_clicks': total_clicks,
        'total_spend': round(total_spend, 2),
        'total_conversions': total_conversions,
        'total_conversion_value': round(total_conversion_value, 2),
        'overall_cpa': round(total_spend / total_conversions, 2) if total_conversions > 0 else 0,
        'overall_roas': round(total_conversion_value / total_spend, 2) if total_spend > 0 else 0,
        'overall_cpm': round(total_spend / total_impressions * 1000, 2) if total_impressions > 0 else 0,
        'overall_cpc': round(total_spend / total_clicks, 2) if total_clicks > 0 else 0,
        'overall_ctr': round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch Facebook/Meta Ads metrics")
    parser.add_argument('--ad_account_id', default=os.getenv('FACEBOOK_AD_ACCOUNT_ID'),
                        help='Facebook Ad Account ID (e.g., act_123456789)')
    parser.add_argument('--start_date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end_date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, default=30,
                        help='Number of days to look back (default: 30)')
    parser.add_argument('--output_dir', default='.tmp',
                        help='Output directory (default: .tmp)')

    args = parser.parse_args()

    # Validate ad account ID
    ad_account_id = args.ad_account_id
    if not ad_account_id:
        print("[ERROR] Ad account ID required. Set FACEBOOK_AD_ACCOUNT_ID in .env or pass --ad_account_id")
        sys.exit(1)

    if not ad_account_id.startswith('act_'):
        ad_account_id = f'act_{ad_account_id}'

    # Calculate date range
    if args.start_date and args.end_date:
        start_date = args.start_date
        end_date = args.end_date
    else:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')

    print(f"\n{'='*70}")
    print(f"FACEBOOK ADS METRICS FETCH")
    print(f"{'='*70}")
    print(f"  Ad Account: {ad_account_id}")
    print(f"  Date Range: {start_date} to {end_date}")
    print(f"{'='*70}\n")

    # Initialize API
    init_facebook_api()

    # Create account object
    account = AdAccount(ad_account_id)

    # Verify account access
    try:
        account_info = account.api_get(fields=['name', 'account_id', 'currency', 'timezone_name', 'account_status'])
        account_name = account_info.get('name', 'Unknown')
        currency = account_info.get('currency', 'USD')
        print(f"  Account Name: {account_name}")
        print(f"  Currency: {currency}")
        print(f"  Timezone: {account_info.get('timezone_name', 'Unknown')}")
        print()
    except Exception as e:
        print(f"[ERROR] Could not access ad account: {e}")
        sys.exit(1)

    # Fetch all data
    campaigns = fetch_campaign_metrics(account, start_date, end_date)
    campaign_daily = fetch_campaign_daily_metrics(account, start_date, end_date)
    ad_sets = fetch_adset_metrics(account, start_date, end_date)
    ads = fetch_ad_metrics(account, start_date, end_date)
    demographics = fetch_demographic_breakdown(account, start_date, end_date)
    placements = fetch_placement_breakdown(account, start_date, end_date)
    geo_data = fetch_geographic_breakdown(account, start_date, end_date)
    time_data = fetch_time_breakdown(account, start_date, end_date)

    # Build summary
    summary = build_summary(campaigns, ad_sets, ads)

    # Build output
    output = {
        'ad_account_id': ad_account_id,
        'account_name': account_name,
        'currency': currency,
        'platform': 'facebook',
        'date_range': {
            'start_date': start_date,
            'end_date': end_date,
        },
        'fetched_at': datetime.now().isoformat(),
        'summary': summary,
        'campaigns': sorted(campaigns, key=lambda x: x['spend'], reverse=True),
        'campaign_daily': sorted(campaign_daily, key=lambda x: (x.get('date') or '', x.get('spend', 0)), reverse=True),
        'ad_sets': sorted(ad_sets, key=lambda x: x['spend'], reverse=True),
        'ads': sorted(ads, key=lambda x: x['spend'], reverse=True),
        'demographic_breakdown': demographics,
        'placement_breakdown': sorted(placements, key=lambda x: x['spend'], reverse=True),
        'geo_performance': sorted(geo_data, key=lambda x: x['clicks'], reverse=True),
        'time_performance': time_data,
    }

    # Save to file
    os.makedirs(args.output_dir, exist_ok=True)
    clean_id = ad_account_id.replace('act_', '')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(args.output_dir, f'facebook_ads_metrics_{clean_id}_{timestamp}.json')

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n{'='*70}")
    print(f"FETCH COMPLETE")
    print(f"{'='*70}")
    print(f"  Output: {output_file}")
    print(f"  Campaigns: {len(campaigns)}")
    print(f"  Daily Campaign Rows: {len(campaign_daily)}")
    print(f"  Ad Sets: {len(ad_sets)}")
    print(f"  Ads: {len(ads)}")
    print(f"  Demographics: {len(demographics)} segments")
    print(f"  Placements: {len(placements)} segments")
    print(f"  Geo: {len(geo_data)} regions")
    print(f"  Daily records: {len(time_data['daily'])}")
    print(f"  Total Spend: {currency} {summary['total_spend']:,.2f}")
    print(f"  Total Conversions: {summary['total_conversions']}")
    print(f"{'='*70}\n")

    return output_file


if __name__ == '__main__':
    main()
