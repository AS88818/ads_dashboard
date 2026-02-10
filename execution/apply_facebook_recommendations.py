#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apply approved Facebook/Meta Ads recommendations.

Handles: audience exclusions, creative refresh, placements, budgets, geo, scheduling.

Usage:
    # Dry run (preview changes)
    python execution/apply_facebook_recommendations.py \
        --ad_account_id act_XXXXX \
        --recommendations_file .tmp/facebook_recommendations_XXXXX.json \
        --approve 1,2,3 \
        --dry_run

    # Apply changes
    python execution/apply_facebook_recommendations.py \
        --ad_account_id act_XXXXX \
        --recommendations_file .tmp/facebook_recommendations_XXXXX.json \
        --approve 1,2,3
"""

import json
import argparse
import os
import sys
import glob

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
from dotenv import load_dotenv
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad

load_dotenv()


def init_facebook_api():
    """Initialize Facebook Ads API."""
    app_id = os.getenv('FACEBOOK_APP_ID')
    app_secret = os.getenv('FACEBOOK_APP_SECRET')
    access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')

    if not all([app_id, app_secret, access_token]):
        raise ValueError("Missing Facebook API credentials in .env")

    FacebookAdsApi.init(app_id, app_secret, access_token)
    return access_token


def get_campaign_id_by_name(account, campaign_name):
    """Get campaign ID from campaign name."""
    campaigns = account.get_campaigns(fields=['id', 'name', 'effective_status'])
    for campaign in campaigns:
        if campaign.get('name') == campaign_name:
            return campaign.get('id')
    return None


def get_adset_id_by_name(account, adset_name):
    """Get ad set ID from ad set name."""
    adsets = account.get_ad_sets(fields=['id', 'name', 'effective_status'])
    for adset in adsets:
        if adset.get('name') == adset_name:
            return adset.get('id')
    return None


def get_ad_id_by_name(account, ad_name):
    """Get ad ID from ad name."""
    ads = account.get_ads(fields=['id', 'name', 'effective_status'])
    for ad in ads:
        if ad.get('name') == ad_name:
            return ad.get('id')
    return None


# ===========================
# Helper Functions for Automation
# ===========================

def parse_age_range(segment_value):
    """
    Parse age range from segment string.

    Args:
        segment_value: String like "18-24", "25-34 Male", or "Female 35-44"

    Returns:
        tuple: (min_age, max_age) or (None, None) if not found
    """
    import re
    # Extract age range pattern: "18-24" or "18 - 24"
    match = re.search(r'(\d{2})\s*-\s*(\d{2})', segment_value)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    # Single age pattern
    match = re.search(r'(\d{2})', segment_value)
    if match:
        age = int(match.group(1))
        return (age, age)
    return (None, None)


def parse_gender(segment_value):
    """
    Parse gender from segment string.

    Args:
        segment_value: String like "Male", "Female", "18-24 Male", etc.

    Returns:
        int: 1 for male, 2 for female, None if not found
    """
    segment_lower = segment_value.lower()
    if 'male' in segment_lower and 'female' not in segment_lower:
        return 1  # Male
    elif 'female' in segment_lower:
        return 2  # Female
    return None


def lookup_location_id(location_name, metrics_data=None):
    """
    Lookup Facebook location ID from metrics geo breakdown or Targeting Search API.

    Args:
        location_name: Location string like "Selangor, MY" or "California"
        metrics_data: Optional metrics JSON with geo_performance data

    Returns:
        tuple: (location_key, location_type) where type is 'region', 'city', or 'country'
               Returns (None, None) if not found
    """
    # Try to find in metrics geo breakdown first
    if metrics_data:
        for geo in metrics_data.get('geo_performance', []):
            if geo.get('location') == location_name:
                # Check if it has a region key
                if geo.get('region_key'):
                    return (geo.get('region_key'), 'region')
                # Otherwise use country code
                if geo.get('country'):
                    return (geo.get('country'), 'country')

    # Fallback: Use Facebook Targeting Search API
    try:
        from facebook_business.adobjects.targetingsearch import TargetingSearch
        # Parse location name to get search query
        search_query = location_name.split(',')[0].strip()  # "Selangor, MY" → "Selangor"

        # Determine location type
        if ',' in location_name:
            # Likely a region/city (has country code)
            location_type = 'region'
            search_type = 'adgeolocation'
        else:
            # Likely a country
            location_type = 'country'
            search_type = 'adgeolocation'

        results = TargetingSearch.search(params={
            'type': search_type,
            'q': search_query
        })

        if results and len(results) > 0:
            # Return the first match
            location_key = results[0].get('key')
            return (location_key, location_type)

    except Exception as e:
        print(f"  Warning: Could not lookup location ID for '{location_name}': {e}")

    return (None, None)


def parse_placement_name(placement_name):
    """
    Parse placement name to platform and position.

    Args:
        placement_name: String like "Instagram - Stories", "Facebook - Feed", etc.

    Returns:
        tuple: (platform, position) or (None, None) if not recognized
    """
    placement_map = {
        'facebook - feed': ('facebook', 'feed'),
        'facebook - right column': ('facebook', 'right_column'),
        'facebook - marketplace': ('facebook', 'marketplace'),
        'facebook - video feeds': ('facebook', 'video_feeds'),
        'facebook - instant article': ('facebook', 'instant_article'),
        'instagram - feed': ('instagram', 'stream'),
        'instagram - stories': ('instagram', 'story'),
        'instagram - explore': ('instagram', 'explore'),
        'instagram - reels': ('instagram', 'reels'),
        'audience network': ('audience_network', None),
        'messenger - inbox': ('messenger', 'messenger_home'),
        'messenger - stories': ('messenger', 'story'),
    }

    key = placement_name.lower().strip()
    return placement_map.get(key, (None, None))


def is_advantage_plus_campaign(campaign_id):
    """
    Check if a campaign is Advantage+ (auto-optimized placements).

    Advantage+ campaigns use automatic placements and cannot exclude specific placements.

    Args:
        campaign_id: Facebook Campaign ID

    Returns:
        bool: True if Advantage+, False otherwise
    """
    try:
        campaign = Campaign(campaign_id)
        campaign_data = campaign.api_get(fields=['objective', 'special_ad_categories'])

        # Advantage+ campaigns typically have OUTCOME_* objectives
        objective = campaign_data.get('objective', '')
        if objective in ['OUTCOME_SALES', 'OUTCOME_LEADS', 'OUTCOME_AWARENESS', 'OUTCOME_TRAFFIC']:
            return True

        return False
    except Exception as e:
        print(f"  Warning: Could not check Advantage+ status for campaign {campaign_id}: {e}")
        return False  # Assume not Advantage+ if we can't check


def adjust_campaign_budget(campaign_id, new_budget_daily=None, new_budget_lifetime=None, dry_run=False):
    """
    Adjust campaign budget (daily or lifetime).

    Args:
        campaign_id: Campaign ID
        new_budget_daily: New daily budget in currency (e.g., 100.00)
        new_budget_lifetime: New lifetime budget in currency
        dry_run: If True, only preview changes
    """
    campaign = Campaign(campaign_id)

    # Fetch current budget
    campaign_data = campaign.api_get(fields=['daily_budget', 'lifetime_budget', 'name'])
    current_daily = float(campaign_data.get('daily_budget', 0)) / 100 if campaign_data.get('daily_budget') else None
    current_lifetime = float(campaign_data.get('lifetime_budget', 0)) / 100 if campaign_data.get('lifetime_budget') else None

    if dry_run:
        msg = f"[DRY RUN] Would update campaign '{campaign_data.get('name')}' budget:"
        if new_budget_daily:
            msg += f"\n  Daily: {current_daily} → {new_budget_daily}"
        if new_budget_lifetime:
            msg += f"\n  Lifetime: {current_lifetime} → {new_budget_lifetime}"
        return {"success": True, "dry_run": True, "message": msg}

    # Apply budget update
    update_data = {}
    if new_budget_daily is not None:
        update_data['daily_budget'] = int(new_budget_daily * 100)  # Convert to cents
    if new_budget_lifetime is not None:
        update_data['lifetime_budget'] = int(new_budget_lifetime * 100)

    try:
        campaign.api_update(params=update_data)
        return {
            "success": True,
            "message": f"Updated campaign '{campaign_data.get('name')}' budget successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to update campaign budget"
        }


def exclude_demographic_segment(adset_id, segment_type, segment_value, dry_run=False):
    """
    Exclude a demographic segment (age/gender) from an ad set.

    Facebook doesn't support direct age exclusions, so we restructure the targeting
    to avoid the excluded segment. Gender exclusions remove the gender from the genders array.

    Args:
        adset_id: Ad Set ID
        segment_type: 'demographic' (age+gender), 'age', 'gender', or 'placement'
        segment_value: The value to exclude (e.g., "18-24 Male", "Female", "25-34")
        dry_run: If True, only preview changes

    Returns:
        Result dict with success status and message
    """
    try:
        adset = AdSet(adset_id)
        adset_data = adset.api_get(fields=['targeting', 'name'])
        # Convert targeting to dict (API may return Targeting object)
        targeting_obj = adset_data.get('targeting', {})
        if hasattr(targeting_obj, 'export_all_data'):
            targeting = dict(targeting_obj.export_all_data())
        else:
            targeting = dict(targeting_obj) if targeting_obj else {}

        changes = []

        # Parse age range from segment
        min_age, max_age = parse_age_range(segment_value)
        if min_age and max_age:
            current_min = targeting.get('age_min', 18)
            current_max = targeting.get('age_max', 65)

            # Adjust age range to exclude segment
            if min_age == current_min and max_age < current_max:
                # Excluding young segment: increase age_min
                targeting['age_min'] = max_age + 1
                changes.append(f"age range {current_min}-{current_max} → {max_age + 1}-{current_max}")
            elif max_age == current_max and min_age > current_min:
                # Excluding old segment: decrease age_max
                targeting['age_max'] = min_age - 1
                changes.append(f"age range {current_min}-{current_max} → {current_min}-{min_age - 1}")
            elif min_age > current_min and max_age < current_max:
                # Excluding middle segment - cannot split range, choose which side to keep
                # Keep the side with more range
                lower_range = min_age - current_min
                upper_range = current_max - max_age
                if upper_range > lower_range:
                    targeting['age_min'] = max_age + 1
                    changes.append(f"age range {current_min}-{current_max} → {max_age + 1}-{current_max} (kept upper range)")
                else:
                    targeting['age_max'] = min_age - 1
                    changes.append(f"age range {current_min}-{current_max} → {current_min}-{min_age - 1} (kept lower range)")

        # Parse gender from segment
        gender_to_exclude = parse_gender(segment_value)
        if gender_to_exclude:
            current_genders = targeting.get('genders', [1, 2])
            if gender_to_exclude in current_genders and len(current_genders) > 1:
                targeting['genders'] = [g for g in current_genders if g != gender_to_exclude]
                gender_name = "Male" if gender_to_exclude == 1 else "Female"
                changes.append(f"removed {gender_name} from targeting")
            elif len(current_genders) == 1:
                return {
                    "success": False,
                    "message": f"Cannot exclude {segment_value}: only one gender currently targeted"
                }

        if not changes:
            return {
                "success": False,
                "message": f"Could not parse exclusion from '{segment_value}'"
            }

        change_summary = ', '.join(changes)

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "message": f"[DRY RUN] Would exclude '{segment_value}' from ad set '{adset_data.get('name')}' ({change_summary})"
            }

        # Apply the targeting update
        adset.api_update(params={'targeting': targeting})

        return {
            "success": True,
            "message": f"X Excluded '{segment_value}' from ad set '{adset_data.get('name')}' ({change_summary})"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to exclude demographic segment: {str(e)}"
        }


def pause_ad(ad_id, dry_run=False):
    """
    Pause an ad (for creative fatigue).

    Args:
        ad_id: Ad ID
        dry_run: If True, only preview changes
    """
    ad = Ad(ad_id)
    ad_data = ad.api_get(fields=['name', 'effective_status'])

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "message": f"[DRY RUN] Would pause ad '{ad_data.get('name')}' (currently: {ad_data.get('effective_status')})"
        }

    try:
        ad.api_update(params={'status': Ad.Status.paused})
        return {
            "success": True,
            "message": f"Paused ad '{ad_data.get('name')}'"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to pause ad"
        }


def exclude_placement(adset_id, placement_name, dry_run=False):
    """
    Exclude a placement from an ad set.

    Removes placement from publisher_platforms and position arrays.
    Cannot exclude placements from Advantage+ campaigns (auto-optimized).

    Args:
        adset_id: Ad Set ID
        placement_name: Placement to exclude (e.g., "Instagram - Stories", "Facebook - Feed")
        dry_run: If True, only preview changes

    Returns:
        Result dict with success status and message
    """
    try:
        adset = AdSet(adset_id)
        adset_data = adset.api_get(fields=['name', 'targeting', 'campaign'])

        # Check if this is an Advantage+ campaign
        campaign_id = adset_data.get('campaign', {}).get('id')
        if campaign_id and is_advantage_plus_campaign(campaign_id):
            return {
                "success": False,
                "message": f"Cannot exclude placements from Advantage+ campaign (uses auto-optimization). Exclusion skipped."
            }

        # Convert targeting to dict (API may return Targeting object)
        targeting_obj = adset_data.get('targeting', {})
        if hasattr(targeting_obj, 'export_all_data'):
            targeting = dict(targeting_obj.export_all_data())
        else:
            targeting = dict(targeting_obj) if targeting_obj else {}

        # Parse placement name
        platform, position = parse_placement_name(placement_name)

        if not platform:
            return {
                "success": False,
                "message": f"Unknown placement format: '{placement_name}'. Expected format like 'Instagram - Stories' or 'Facebook - Feed'"
            }

        changes = []

        # Get current platforms
        platforms = targeting.get('publisher_platforms', ['facebook', 'instagram'])

        # Remove position from platform-specific array
        if platform == 'facebook' and position:
            fb_positions = targeting.get('facebook_positions', [])
            if position in fb_positions:
                targeting['facebook_positions'] = [p for p in fb_positions if p != position]
                changes.append(f"removed '{position}' from Facebook positions")
                # If no positions left, remove Facebook entirely
                if not targeting.get('facebook_positions'):
                    platforms = [p for p in platforms if p != 'facebook']
                    changes.append("removed Facebook platform (no positions left)")

        elif platform == 'instagram' and position:
            ig_positions = targeting.get('instagram_positions', [])
            if position in ig_positions:
                targeting['instagram_positions'] = [p for p in ig_positions if p != position]
                changes.append(f"removed '{position}' from Instagram positions")
                # If no positions left, remove Instagram entirely
                if not targeting.get('instagram_positions'):
                    platforms = [p for p in platforms if p != 'instagram']
                    changes.append("removed Instagram platform (no positions left)")

        elif platform == 'audience_network':
            # Remove entire platform
            if 'audience_network' in platforms:
                platforms = [p for p in platforms if p != 'audience_network']
                changes.append("removed Audience Network platform")

        elif platform == 'messenger' and position:
            messenger_positions = targeting.get('messenger_positions', [])
            if position in messenger_positions:
                targeting['messenger_positions'] = [p for p in messenger_positions if p != position]
                changes.append(f"removed '{position}' from Messenger positions")
                if not targeting.get('messenger_positions'):
                    platforms = [p for p in platforms if p != 'messenger']
                    changes.append("removed Messenger platform (no positions left)")

        if not changes:
            return {
                "success": False,
                "message": f"Placement '{placement_name}' not found in ad set targeting or already excluded"
            }

        # Check if we're removing all platforms (would break the ad set)
        if not platforms or len(platforms) == 0:
            return {
                "success": False,
                "message": f"Cannot exclude '{placement_name}': would remove all placements from ad set. Keep at least one platform."
            }

        targeting['publisher_platforms'] = platforms
        change_summary = ', '.join(changes)

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "message": f"[DRY RUN] Would exclude placement '{placement_name}' from ad set '{adset_data.get('name')}' ({change_summary})"
            }

        # Apply the targeting update
        adset.api_update(params={'targeting': targeting})

        return {
            "success": True,
            "message": f"X Excluded placement '{placement_name}' from ad set '{adset_data.get('name')}' ({change_summary})"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to exclude placement: {str(e)}"
        }


def exclude_geo_location(adset_id, location_name, metrics_data=None, dry_run=False):
    """
    Exclude a geographic location from an ad set.

    Uses metrics data or Facebook Targeting Search API to lookup location ID,
    then adds it to excluded_regions or excluded_countries in targeting.

    Args:
        adset_id: Ad Set ID
        location_name: Location to exclude (e.g., "Selangor, MY")
        metrics_data: Optional metrics JSON with geo_performance data
        dry_run: If True, only preview changes

    Returns:
        Result dict with success status and message
    """
    try:
        adset = AdSet(adset_id)
        adset_data = adset.api_get(fields=['name', 'targeting'])
        # Convert targeting to dict (API may return Targeting object)
        targeting_obj = adset_data.get('targeting', {})
        if hasattr(targeting_obj, 'export_all_data'):
            targeting = dict(targeting_obj.export_all_data())
        else:
            targeting = dict(targeting_obj) if targeting_obj else {}

        # Lookup location ID
        location_key, location_type = lookup_location_id(location_name, metrics_data)

        if not location_key:
            return {
                "success": False,
                "message": f"Could not find location ID for '{location_name}'. Try manual exclusion in Ads Manager."
            }

        # Get current geo_locations
        geo_locs = targeting.get('geo_locations', {})

        # Add to appropriate exclusion list based on type
        if location_type == 'region':
            excluded = geo_locs.get('excluded_regions', [])
            # Check if already excluded
            if any(r.get('key') == location_key for r in excluded):
                return {
                    "success": False,
                    "message": f"Location '{location_name}' is already excluded from ad set '{adset_data.get('name')}'"
                }
            excluded.append({'key': str(location_key), 'name': location_name})
            geo_locs['excluded_regions'] = excluded
        elif location_type == 'city':
            excluded = geo_locs.get('excluded_cities', [])
            if any(c.get('key') == location_key for c in excluded):
                return {
                    "success": False,
                    "message": f"Location '{location_name}' is already excluded"
                }
            excluded.append({'key': str(location_key), 'name': location_name})
            geo_locs['excluded_cities'] = excluded
        elif location_type == 'country':
            excluded = geo_locs.get('excluded_countries', [])
            if location_key in excluded:
                return {
                    "success": False,
                    "message": f"Country '{location_name}' is already excluded"
                }
            excluded.append(location_key)
            geo_locs['excluded_countries'] = excluded

        targeting['geo_locations'] = geo_locs

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "message": f"[DRY RUN] Would exclude {location_type} '{location_name}' (ID: {location_key}) from ad set '{adset_data.get('name')}'"
            }

        # Apply the targeting update
        adset.api_update(params={'targeting': targeting})

        return {
            "success": True,
            "message": f"X Excluded {location_type} '{location_name}' from ad set '{adset_data.get('name')}'"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to exclude location: {str(e)}"
        }


def adjust_ad_schedule(adset_id, best_hours, dry_run=False):
    """
    Adjust ad scheduling (day-parting) to focus budget on peak hours.

    Facebook adset_schedule format: Array of time windows per day.
    Each entry has: start_minute (0-1439), end_minute (0-1439), days (0=Sunday...6=Saturday)

    Args:
        adset_id: Ad Set ID
        best_hours: List of peak hours (integers 0-23), e.g., [14, 15, 16]
        dry_run: If True, only preview changes

    Returns:
        Result dict with success status and message
    """
    try:
        adset = AdSet(adset_id)
        adset_data = adset.api_get(fields=['name', 'adset_schedule', 'campaign'])

        # Check if campaign supports day-parting (Advantage+ campaigns don't)
        campaign_id = adset_data.get('campaign', {}).get('id')
        if campaign_id and is_advantage_plus_campaign(campaign_id):
            return {
                "success": False,
                "message": f"Cannot set ad schedule for Advantage+ campaign (uses automatic scheduling). Schedule adjustment skipped."
            }

        # Build schedule array for all 7 days, enabling only peak hours
        # Note: Facebook requires end_minute to be on hour boundaries (0, 60, 120, etc.)
        schedule = []
        for hour in best_hours:
            schedule.append({
                'start_minute': hour * 60,         # Convert hour to minutes (e.g., 14:00 = 840 minutes)
                'end_minute': (hour + 1) * 60,     # Next hour boundary (e.g., 15:00 = 900 minutes)
                'days': [0, 1, 2, 3, 4, 5, 6],     # All days (Sunday=0 through Saturday=6)
                'timezone_type': 'USER'             # Use user's timezone
            })

        hours_str = ', '.join([f"{h}:00-{h}:59" for h in best_hours])

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "message": f"[DRY RUN] Would schedule ad set '{adset_data.get('name')}' for hours: {hours_str} daily"
            }

        # Update the ad set with new schedule
        adset.api_update(params={'adset_schedule': schedule})

        return {
            "success": True,
            "message": f"X Scheduled ad set '{adset_data.get('name')}' for peak hours: {hours_str} daily"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to adjust ad schedule: {str(e)}"
        }


def pause_campaign(campaign_id, dry_run=False):
    """
    Pause an entire campaign.

    Args:
        campaign_id: Campaign ID
        dry_run: If True, only preview changes
    """
    campaign = Campaign(campaign_id)
    campaign_data = campaign.api_get(fields=['name', 'effective_status'])

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "message": f"[DRY RUN] Would pause campaign '{campaign_data.get('name')}' (currently: {campaign_data.get('effective_status')})"
        }

    try:
        campaign.api_update(params={'status': Campaign.Status.paused})
        return {
            "success": True,
            "message": f"Paused campaign '{campaign_data.get('name')}'"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to pause campaign: {str(e)}"
        }


def scale_campaign_budget(campaign_id, scale_factor, dry_run=False):
    """
    Scale a campaign's budget by a factor (e.g., 1.25 = +25%, 0.5 = -50%).

    Fetches the current daily budget and applies the scale factor.

    Args:
        campaign_id: Campaign ID
        scale_factor: Multiplier (e.g., 1.25 for +25%, 0.50 for -50%)
        dry_run: If True, only preview changes
    """
    campaign = Campaign(campaign_id)
    campaign_data = campaign.api_get(fields=['daily_budget', 'lifetime_budget', 'name'])

    current_daily = float(campaign_data.get('daily_budget', 0)) / 100 if campaign_data.get('daily_budget') else None
    current_lifetime = float(campaign_data.get('lifetime_budget', 0)) / 100 if campaign_data.get('lifetime_budget') else None

    if current_daily:
        new_budget = round(current_daily * scale_factor, 2)
        pct_change = int((scale_factor - 1) * 100)
        sign = '+' if pct_change > 0 else ''

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "message": f"[DRY RUN] Would scale campaign '{campaign_data.get('name')}' daily budget: "
                           f"{current_daily:.2f} -> {new_budget:.2f} ({sign}{pct_change}%)"
            }

        return adjust_campaign_budget(campaign_id, new_budget_daily=new_budget, dry_run=False)

    elif current_lifetime:
        new_budget = round(current_lifetime * scale_factor, 2)
        pct_change = int((scale_factor - 1) * 100)
        sign = '+' if pct_change > 0 else ''

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "message": f"[DRY RUN] Would scale campaign '{campaign_data.get('name')}' lifetime budget: "
                           f"{current_lifetime:.2f} -> {new_budget:.2f} ({sign}{pct_change}%)"
            }

        return adjust_campaign_budget(campaign_id, new_budget_lifetime=new_budget, dry_run=False)

    else:
        return {
            "success": False,
            "message": f"Campaign '{campaign_data.get('name')}' has no budget set (may use ad set budgets instead)"
        }


def adjust_day_schedule(adset_id, wasted_day_names, dry_run=False):
    """
    Adjust ad schedule to exclude wasted days (days with zero conversions).

    Builds a schedule that runs ads all hours on non-wasted days only.

    Args:
        adset_id: Ad Set ID
        wasted_day_names: List of day name strings to exclude (e.g., ['Monday', 'Thursday'])
        dry_run: If True, only preview changes
    """
    try:
        adset = AdSet(adset_id)
        adset_data = adset.api_get(fields=['name', 'campaign'])

        # Check Advantage+ compatibility
        campaign_id = adset_data.get('campaign', {}).get('id')
        if campaign_id and is_advantage_plus_campaign(campaign_id):
            return {
                "success": False,
                "message": f"Cannot set day schedule for Advantage+ campaign. Schedule adjustment skipped."
            }

        # Map day names to Facebook day numbers (0=Sunday, 1=Monday, ..., 6=Saturday)
        day_map = {
            'sunday': 0, 'monday': 1, 'tuesday': 2, 'wednesday': 3,
            'thursday': 4, 'friday': 5, 'saturday': 6
        }

        wasted_day_nums = set()
        for day_name in wasted_day_names:
            day_num = day_map.get(day_name.lower().strip())
            if day_num is not None:
                wasted_day_nums.add(day_num)

        if not wasted_day_nums:
            return {
                "success": False,
                "message": f"Could not parse wasted days: {wasted_day_names}"
            }

        # Build schedule: run all hours (0-24) on non-wasted days only
        active_days = [d for d in range(7) if d not in wasted_day_nums]

        if not active_days:
            return {
                "success": False,
                "message": "Cannot exclude all days of the week"
            }

        schedule = [{
            'start_minute': 0,
            'end_minute': 1440,  # Full day (24 hours * 60 minutes)
            'days': active_days,
            'timezone_type': 'USER'
        }]

        excluded_names = ', '.join(wasted_day_names)

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "message": f"[DRY RUN] Would exclude {excluded_names} from ad set '{adset_data.get('name')}' schedule"
            }

        adset.api_update(params={'adset_schedule': schedule})

        return {
            "success": True,
            "message": f"Excluded {excluded_names} from ad set '{adset_data.get('name')}' schedule"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to adjust day schedule: {str(e)}"
        }


def apply_recommendation(account, rec, metrics_data=None, dry_run=False):
    """
    Apply a single recommendation.

    Args:
        account: Facebook Ad Account object
        rec: Recommendation dictionary
        metrics_data: Optional metrics JSON for location ID lookup
        dry_run: If True, only preview changes

    Returns:
        Result dictionary with success status and message
    """
    rec_type = rec.get('type')

    try:
        if rec_type == 'budget_adjustment':
            # Get campaign ID
            campaign_name = rec.get('campaign_name')
            campaign_id = get_campaign_id_by_name(account, campaign_name)

            if not campaign_id:
                return {
                    "success": False,
                    "message": f"Campaign '{campaign_name}' not found"
                }

            # For now, we'll increase budget by 20% (user can customize this)
            # In production, this should be configurable or prompted
            campaign = Campaign(campaign_id)
            campaign_data = campaign.api_get(fields=['daily_budget', 'name'])

            if campaign_data.get('daily_budget'):
                current_budget = float(campaign_data.get('daily_budget')) / 100
                new_budget = current_budget * 1.2  # 20% increase

                return adjust_campaign_budget(
                    campaign_id,
                    new_budget_daily=new_budget,
                    dry_run=dry_run
                )
            else:
                return {
                    "success": False,
                    "message": f"Campaign has no daily budget set"
                }

        elif rec_type == 'audience_exclusion':
            # Get ad set ID
            adset_id = rec.get('adset_id')
            if not adset_id:
                adset_name = rec.get('adset_name')
                adset_id = get_adset_id_by_name(account, adset_name) if adset_name else None

            if not adset_id:
                return {
                    "success": False,
                    "message": f"No ad set specified for audience exclusion. Recommendation data missing adset_id."
                }

            return exclude_demographic_segment(
                adset_id=adset_id,
                segment_type=rec.get('segment_type', 'demographic'),
                segment_value=rec.get('segment'),
                dry_run=dry_run
            )

        elif rec_type == 'creative_refresh':
            # Pause fatigued ad
            ad_name = rec.get('ad_name')
            ad_id = get_ad_id_by_name(account, ad_name)

            if not ad_id:
                return {
                    "success": False,
                    "message": f"Ad '{ad_name}' not found"
                }

            return pause_ad(ad_id, dry_run=dry_run)

        elif rec_type == 'placement_exclusion':
            # Get ad set ID
            adset_id = rec.get('adset_id')
            if not adset_id:
                adset_name = rec.get('adset_name')
                adset_id = get_adset_id_by_name(account, adset_name) if adset_name else None

            if not adset_id:
                return {
                    "success": False,
                    "message": f"No ad set specified for placement exclusion. Recommendation data missing adset_id."
                }

            return exclude_placement(
                adset_id=adset_id,
                placement_name=rec.get('placement'),
                dry_run=dry_run
            )

        elif rec_type == 'geo_exclusion':
            # Get ad set ID
            adset_id = rec.get('adset_id')
            if not adset_id:
                adset_name = rec.get('adset_name')
                adset_id = get_adset_id_by_name(account, adset_name) if adset_name else None

            if not adset_id:
                return {
                    "success": False,
                    "message": f"No ad set specified for geo exclusion. Recommendation data missing adset_id."
                }

            return exclude_geo_location(
                adset_id=adset_id,
                location_name=rec.get('location'),
                metrics_data=metrics_data,
                dry_run=dry_run
            )

        elif rec_type == 'schedule_adjustment':
            # Get ad set ID
            adset_id = rec.get('adset_id')
            if not adset_id:
                adset_name = rec.get('adset_name')
                adset_id = get_adset_id_by_name(account, adset_name) if adset_name else None

            if not adset_id:
                return {
                    "success": False,
                    "message": f"No ad set specified for schedule adjustment. Recommendation data missing adset_id."
                }

            best_hours = rec.get('best_hours', [])
            if not best_hours:
                return {
                    "success": False,
                    "message": f"No peak hours specified for schedule adjustment. Recommendation data missing best_hours."
                }

            return adjust_ad_schedule(
                adset_id=adset_id,
                best_hours=best_hours,
                dry_run=dry_run
            )

        elif rec_type == 'budget_scaling':
            # Scale budget up 25% for top-performing campaigns
            campaign_name = rec.get('campaign_name')
            campaign_id = get_campaign_id_by_name(account, campaign_name)

            if not campaign_id:
                return {
                    "success": False,
                    "message": f"Campaign '{campaign_name}' not found"
                }

            return scale_campaign_budget(campaign_id, scale_factor=1.25, dry_run=dry_run)

        elif rec_type == 'campaign_review':
            # Pause underperforming campaign (zero conversions, high spend)
            campaign_name = rec.get('campaign_name')
            campaign_id = get_campaign_id_by_name(account, campaign_name)

            if not campaign_id:
                return {
                    "success": False,
                    "message": f"Campaign '{campaign_name}' not found"
                }

            return pause_campaign(campaign_id, dry_run=dry_run)

        elif rec_type == 'roas_scaling':
            # Scale budget up 30% for high-ROAS campaigns
            campaign_name = rec.get('campaign_name') or rec.get('name')
            if not campaign_name:
                # Try to extract from action text
                action = rec.get('action', '')
                if 'Scale ' in action:
                    campaign_name = action.split('Scale ')[1].split(' (')[0]

            campaign_id = get_campaign_id_by_name(account, campaign_name) if campaign_name else None

            if not campaign_id:
                return {
                    "success": False,
                    "message": f"Campaign '{campaign_name}' not found for ROAS scaling"
                }

            return scale_campaign_budget(campaign_id, scale_factor=1.30, dry_run=dry_run)

        elif rec_type == 'roas_review':
            # Cut budget 50% for low-ROAS campaigns (losing money)
            campaign_name = rec.get('campaign_name') or rec.get('name')
            if not campaign_name:
                action = rec.get('action', '')
                if 'Review ' in action:
                    campaign_name = action.split('Review ')[1].split(' (')[0]

            campaign_id = get_campaign_id_by_name(account, campaign_name) if campaign_name else None

            if not campaign_id:
                return {
                    "success": False,
                    "message": f"Campaign '{campaign_name}' not found for ROAS review"
                }

            return scale_campaign_budget(campaign_id, scale_factor=0.50, dry_run=dry_run)

        elif rec_type == 'geo_scaling':
            # Increase budget 20% for campaigns targeting high-performing locations
            # Since geo-level budget control isn't available, we scale the campaign budget
            campaign_name = rec.get('campaign_name')
            if not campaign_name:
                # Use first active campaign as fallback
                campaigns = account.get_campaigns(
                    fields=['id', 'name', 'effective_status'],
                    params={'effective_status': ['ACTIVE']}
                )
                for camp in campaigns:
                    campaign_name = camp.get('name')
                    break

            campaign_id = get_campaign_id_by_name(account, campaign_name) if campaign_name else None

            if not campaign_id:
                return {
                    "success": False,
                    "message": f"No active campaign found for geo scaling"
                }

            location = rec.get('location', 'unknown location')
            result = scale_campaign_budget(campaign_id, scale_factor=1.20, dry_run=dry_run)
            if result.get('success'):
                result['message'] += f" (driven by strong performance in {location})"
            return result

        elif rec_type == 'day_schedule':
            # Exclude wasted days from ad schedule
            # Parse wasted day names from recommendation action text
            action = rec.get('action', '')
            # Action format: "Reduce spend on Monday, Thursday"
            wasted_days = []
            if 'Reduce spend on ' in action:
                days_str = action.split('Reduce spend on ')[1]
                wasted_days = [d.strip() for d in days_str.split(',')]

            if not wasted_days:
                return {
                    "success": False,
                    "message": "Could not parse wasted days from recommendation"
                }

            # Get ad set to apply schedule to
            adset_id = rec.get('adset_id')
            if not adset_id:
                adset_name = rec.get('adset_name')
                adset_id = get_adset_id_by_name(account, adset_name) if adset_name else None

            if not adset_id:
                # Fallback: get first active ad set
                adsets = account.get_ad_sets(
                    fields=['id', 'name', 'effective_status'],
                    params={'effective_status': ['ACTIVE']}
                )
                for adset in adsets:
                    adset_id = adset.get('id')
                    break

            if not adset_id:
                return {
                    "success": False,
                    "message": "No active ad set found for day schedule adjustment"
                }

            return adjust_day_schedule(adset_id, wasted_days, dry_run=dry_run)

        # --- Manual-only recommendation types ---
        elif rec_type == 'audience_fatigue':
            return {
                "success": False,
                "message": f"MANUAL ACTION: {rec.get('action', 'Expand audience')}. "
                           f"Go to Ads Manager > Ad Set > Audience section to expand targeting or create a lookalike audience. "
                           f"Reason: {rec.get('reason', 'High frequency detected')}"
            }

        elif rec_type == 'objective_mismatch':
            return {
                "success": False,
                "message": f"MANUAL ACTION: {rec.get('action', 'Change campaign objective')}. "
                           f"Facebook does not allow changing campaign objectives after creation. "
                           f"Create a new campaign with the recommended objective and pause the old one. "
                           f"Reason: {rec.get('reason', '')}"
            }

        elif rec_type == 'creative_test':
            return {
                "success": False,
                "message": f"MANUAL ACTION: {rec.get('action', 'Test new creatives')}. "
                           f"Create new ad variations in Ads Manager to A/B test. "
                           f"Reason: {rec.get('reason', '')}"
            }

        elif rec_type == 'landing_page':
            return {
                "success": False,
                "message": f"MANUAL ACTION: {rec.get('action', 'Optimize landing page')}. "
                           f"Landing page changes must be made on your website. "
                           f"Reason: {rec.get('reason', '')}"
            }

        else:
            return {
                "success": False,
                "message": f"Unknown recommendation type: {rec_type}"
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Error applying recommendation: {str(e)}"
        }


def main():
    parser = argparse.ArgumentParser(description="Apply Facebook Ads recommendations")
    parser.add_argument('--ad_account_id', required=True, help='Facebook Ad Account ID (act_XXXXX)')
    parser.add_argument('--recommendations_file', required=True, help='Path to recommendations JSON')
    parser.add_argument('--approve', help='Comma-separated list of recommendation numbers to approve (e.g., 1,2,5)')
    parser.add_argument('--dry_run', action='store_true', help='Preview changes without applying')

    args = parser.parse_args()

    # Initialize Facebook API
    try:
        init_facebook_api()
    except Exception as e:
        print(f"[ERROR] Failed to initialize Facebook API: {e}")
        return

    # Load recommendations
    if not os.path.exists(args.recommendations_file):
        print(f"[ERROR] Recommendations file not found: {args.recommendations_file}")
        return

    with open(args.recommendations_file, 'r') as f:
        recommendations = json.load(f)

    if not recommendations:
        print("[INFO] No recommendations to apply")
        return

    # Load metrics data for location ID lookups (optional, for geo exclusions)
    metrics_data = None
    metrics_file_pattern = f".tmp/facebook_ads_metrics_{args.ad_account_id.replace('act_', '')}_*.json"
    metrics_files = glob.glob(metrics_file_pattern)
    if metrics_files:
        # Get the most recent metrics file
        latest_metrics = max(metrics_files, key=os.path.getmtime)
        try:
            with open(latest_metrics, 'r') as f:
                metrics_data = json.load(f)
        except Exception as e:
            print(f"[WARNING] Could not load metrics file for location lookups: {e}")
            print(f"  Geographic exclusions may use fallback API lookups")

    # Get approved indices
    approved_indices = []
    if args.approve:
        try:
            approved_indices = [int(x.strip()) for x in args.approve.split(',')]
        except ValueError:
            print("[ERROR] Invalid --approve format. Use comma-separated numbers (e.g., 1,2,5)")
            return

    # Initialize account
    account = AdAccount(args.ad_account_id)

    print(f"\n{'='*70}")
    print(f"FACEBOOK ADS RECOMMENDATIONS - {'DRY RUN' if args.dry_run else 'LIVE EXECUTION'}")
    print(f"{'='*70}")
    print(f"  Account: {args.ad_account_id}")
    print(f"  Total Recommendations: {len(recommendations)}")
    print(f"  Approved: {len(approved_indices) if approved_indices else 'None'}")
    print(f"{'='*70}\n")

    # Display all recommendations
    print("RECOMMENDATIONS:")
    for i, rec in enumerate(recommendations, 1):
        priority = rec.get('priority', 'medium').upper()
        action = rec.get('action', 'Unknown action')
        reason = rec.get('reason', '')
        impact = rec.get('expected_impact', '')

        approved_marker = "X" if i in approved_indices else " "
        print(f"\n{i}. [{approved_marker}] [{priority}] {action}")
        print(f"   Reason: {reason}")
        print(f"   Impact: {impact}")

    # Apply approved recommendations
    if not approved_indices:
        print("\n[INFO] No recommendations approved. Use --approve to select recommendations.")
        return

    print(f"\n{'='*70}")
    print(f"APPLYING {len(approved_indices)} RECOMMENDATIONS...")
    print(f"{'='*70}\n")

    results = {"success": 0, "failed": 0, "manual": 0}

    for idx in approved_indices:
        if idx < 1 or idx > len(recommendations):
            print(f"[WARNING] Invalid recommendation number: {idx}")
            continue

        rec = recommendations[idx - 1]
        print(f"\nProcessing recommendation #{idx}: {rec.get('type')} - {rec.get('action')[:60]}")

        result = apply_recommendation(account, rec, metrics_data=metrics_data, dry_run=args.dry_run)

        if result.get('success'):
            if result.get('dry_run'):
                print(f"[OK] DRY RUN")
            else:
                print(f"[OK] SUCCESS")
                results["success"] += 1
            print(f"  {result.get('message', '')}")
        else:
            # Check if it's a manual action
            if "manual implementation" in result.get('message', ''):
                print(f"[!] MANUAL ACTION REQUIRED")
                results["manual"] += 1
            else:
                print(f"[X] FAILED")
                results["failed"] += 1

            print(f"  {result.get('message', '')}")
            if result.get('error'):
                print(f"  Error: {result.get('error')}")

    # Summary
    print(f"\n{'='*70}")
    print(f"EXECUTION SUMMARY")
    print(f"{'='*70}")
    if args.dry_run:
        print(f"  Mode: DRY RUN (no changes applied)")
    else:
        print(f"  Successful: {results['success']}")
        print(f"  Failed: {results['failed']}")
        print(f"  Manual: {results['manual']}")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    main()
