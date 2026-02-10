#!/usr/bin/env python3
"""
Apply approved Google Ads recommendations.
Handles: keywords, bids, schedules, geo, ad copy, and extensions.
"""

import json
import argparse
import os
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.protobuf import field_mask_pb2

# Load environment variables
load_dotenv()


def load_google_ads_client():
    """Initialize Google Ads API client from environment variables."""
    login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")

    # Remove dashes if present and validate
    login_customer_id = login_customer_id.replace("-", "").strip()

    credentials = {
        "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": os.getenv("GOOGLE_ADS_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
        "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
        "token_uri": "https://oauth2.googleapis.com/token",
        "use_proto_plus": True
    }

    # Add login_customer_id only if present
    if login_customer_id:
        credentials["login_customer_id"] = login_customer_id

    return GoogleAdsClient.load_from_dict(credentials)


def get_campaign_from_ad_group(client, customer_id, ad_group_name):
    """
    Get campaign ID from ad group name.

    Args:
        client: Google Ads client
        customer_id: Customer ID
        ad_group_name: Name of the ad group

    Returns:
        Campaign ID or None if not found
    """
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            ad_group.id,
            ad_group.name,
            ad_group.campaign
        FROM ad_group
        WHERE ad_group.name = '{ad_group_name}'
        LIMIT 1
    """

    try:
        response = ga_service.search(customer_id=customer_id, query=query)

        for row in response:
            # Extract campaign ID from resource name
            # Format: customers/123/campaigns/456
            campaign_resource = row.ad_group.campaign
            campaign_id = campaign_resource.split('/')[-1]
            return campaign_id

        return None

    except GoogleAdsException as ex:
        print(f"Error fetching campaign for ad group '{ad_group_name}': {ex}")
        return None


def add_negative_keyword(client, customer_id, campaign_id, negative_keyword, match_type="PHRASE"):
    """
    Add a negative keyword to a campaign.

    Args:
        client: Google Ads client
        customer_id: Customer ID
        campaign_id: Campaign ID
        negative_keyword: The keyword text to add as negative
        match_type: BROAD, PHRASE, or EXACT (default: PHRASE)
    """
    campaign_criterion_service = client.get_service("CampaignCriterionService")

    # Create campaign criterion operation
    campaign_criterion_operation = client.get_type("CampaignCriterionOperation")
    campaign_criterion = campaign_criterion_operation.create

    campaign_criterion.campaign = client.get_service("CampaignService").campaign_path(
        customer_id, campaign_id
    )
    campaign_criterion.negative = True
    campaign_criterion.keyword.text = negative_keyword
    campaign_criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[match_type]

    try:
        response = campaign_criterion_service.mutate_campaign_criteria(
            customer_id=customer_id,
            operations=[campaign_criterion_operation]
        )
        return {
            "success": True,
            "resource_name": response.results[0].resource_name,
            "message": f"Added negative keyword: {negative_keyword} ({match_type})"
        }
    except GoogleAdsException as ex:
        return {
            "success": False,
            "error": str(ex),
            "message": f"Failed to add negative keyword: {negative_keyword}"
        }


def change_keyword_match_type(client, customer_id, ad_group_criterion_resource_name, new_match_type):
    """
    Change the match type of an existing keyword.
    Note: Google Ads API doesn't allow modifying match type directly.
    Instead, we need to create a new keyword with the new match type.

    Args:
        client: Google Ads client
        customer_id: Customer ID
        ad_group_criterion_resource_name: Resource name of the keyword
        new_match_type: BROAD, PHRASE, or EXACT
    """
    # First, get the current keyword details
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            ad_group_criterion.criterion_id,
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.ad_group,
            ad_group_criterion.cpc_bid_micros
        FROM ad_group_criterion
        WHERE ad_group_criterion.resource_name = '{ad_group_criterion_resource_name}'
    """

    try:
        response = ga_service.search(customer_id=customer_id, query=query)

        for row in response:
            keyword_text = row.ad_group_criterion.keyword.text
            ad_group = row.ad_group_criterion.ad_group
            cpc_bid_micros = row.ad_group_criterion.cpc_bid_micros

            # Create new keyword with new match type
            ad_group_criterion_service = client.get_service("AdGroupCriterionService")
            ad_group_criterion_operation = client.get_type("AdGroupCriterionOperation")

            # Create new criterion
            new_criterion = ad_group_criterion_operation.create
            new_criterion.ad_group = ad_group
            new_criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
            new_criterion.keyword.text = keyword_text
            new_criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[new_match_type]
            new_criterion.cpc_bid_micros = cpc_bid_micros

            # Add the new keyword
            new_response = ad_group_criterion_service.mutate_ad_group_criteria(
                customer_id=customer_id,
                operations=[ad_group_criterion_operation]
            )

            return {
                "success": True,
                "message": f"Created new keyword '{keyword_text}' with {new_match_type} match type. Original keyword still exists - please pause it manually or use the pause action.",
                "new_resource_name": new_response.results[0].resource_name,
                "note": "You now have both the old (broad) and new (phrase/exact) keyword. Consider pausing the old one."
            }

    except GoogleAdsException as ex:
        return {
            "success": False,
            "error": str(ex),
            "message": f"Failed to change match type"
        }


def pause_keyword(client, customer_id, ad_group_criterion_resource_name):
    """
    Pause a keyword.

    Args:
        client: Google Ads client
        customer_id: Customer ID
        ad_group_criterion_resource_name: Resource name of the keyword to pause
    """
    ad_group_criterion_service = client.get_service("AdGroupCriterionService")
    ad_group_criterion_operation = client.get_type("AdGroupCriterionOperation")

    ad_group_criterion = ad_group_criterion_operation.update
    ad_group_criterion.resource_name = ad_group_criterion_resource_name
    ad_group_criterion.status = client.enums.AdGroupCriterionStatusEnum.PAUSED

    # Set the update mask
    ad_group_criterion_operation.update_mask.CopyFrom(
        field_mask_pb2.FieldMask(paths=["status"])
    )

    try:
        response = ad_group_criterion_service.mutate_ad_group_criteria(
            customer_id=customer_id,
            operations=[ad_group_criterion_operation]
        )
        return {
            "success": True,
            "resource_name": response.results[0].resource_name,
            "message": f"Keyword paused successfully"
        }
    except GoogleAdsException as ex:
        return {
            "success": False,
            "error": str(ex),
            "message": f"Failed to pause keyword"
        }


def adjust_keyword_bid(client, customer_id, ad_group_criterion_resource_name, new_bid):
    """
    Adjust the bid of a keyword.

    Args:
        client: Google Ads client
        customer_id: Customer ID
        ad_group_criterion_resource_name: Resource name of the keyword
        new_bid: New bid in currency units (will be converted to micros)
    """
    ad_group_criterion_service = client.get_service("AdGroupCriterionService")
    ad_group_criterion_operation = client.get_type("AdGroupCriterionOperation")

    ad_group_criterion = ad_group_criterion_operation.update
    ad_group_criterion.resource_name = ad_group_criterion_resource_name
    # Round to nearest 0.01 (10,000 micros) to meet billable unit requirement
    bid_micros = round(new_bid * 1_000_000 / 10_000) * 10_000
    ad_group_criterion.cpc_bid_micros = int(bid_micros)

    # Set the update mask
    ad_group_criterion_operation.update_mask.CopyFrom(
        field_mask_pb2.FieldMask(paths=["cpc_bid_micros"])
    )

    try:
        response = ad_group_criterion_service.mutate_ad_group_criteria(
            customer_id=customer_id,
            operations=[ad_group_criterion_operation]
        )
        return {
            "success": True,
            "resource_name": response.results[0].resource_name,
            "message": f"Bid adjusted to {new_bid:.2f}"
        }
    except GoogleAdsException as ex:
        return {
            "success": False,
            "error": str(ex),
            "message": f"Failed to adjust bid"
        }


def apply_schedule_bid_adjustment(client, customer_id, campaign_id, day_of_week, start_hour, end_hour, bid_modifier):
    """
    Apply ad schedule bid adjustment.

    Args:
        client: Google Ads client
        customer_id: Customer ID
        campaign_id: Campaign ID
        day_of_week: Day of week (MONDAY, TUESDAY, etc.)
        start_hour: Start hour (0-23)
        end_hour: End hour (0-23)
        bid_modifier: Bid modifier (e.g., 1.3 for +30%, 0.7 for -30%)
    """
    campaign_criterion_service = client.get_service("CampaignCriterionService")
    campaign_criterion_operation = client.get_type("CampaignCriterionOperation")

    campaign_criterion = campaign_criterion_operation.create
    campaign_criterion.campaign = client.get_service("CampaignService").campaign_path(
        customer_id, campaign_id
    )

    # Set ad schedule
    campaign_criterion.ad_schedule.day_of_week = client.enums.DayOfWeekEnum[day_of_week]
    campaign_criterion.ad_schedule.start_hour = start_hour
    campaign_criterion.ad_schedule.end_hour = end_hour
    campaign_criterion.ad_schedule.start_minute = client.enums.MinuteOfHourEnum.ZERO
    campaign_criterion.ad_schedule.end_minute = client.enums.MinuteOfHourEnum.ZERO

    # Set bid modifier
    campaign_criterion.bid_modifier = bid_modifier

    try:
        response = campaign_criterion_service.mutate_campaign_criteria(
            customer_id=customer_id,
            operations=[campaign_criterion_operation]
        )
        return {
            "success": True,
            "resource_name": response.results[0].resource_name,
            "message": f"Applied schedule bid adjustment: {day_of_week} {start_hour}:00-{end_hour}:00 at {bid_modifier:.0%}"
        }
    except GoogleAdsException as ex:
        return {
            "success": False,
            "error": str(ex),
            "message": f"Failed to apply schedule bid adjustment"
        }


def apply_geo_bid_adjustment(client, customer_id, campaign_id, location_id, bid_modifier):
    """
    Apply geographic bid adjustment.

    Args:
        client: Google Ads client
        customer_id: Customer ID
        campaign_id: Campaign ID
        location_id: Geographic location criterion ID
        bid_modifier: Bid modifier (e.g., 0.65 for -35%, 1.3 for +30%)
    """
    campaign_criterion_service = client.get_service("CampaignCriterionService")
    campaign_criterion_operation = client.get_type("CampaignCriterionOperation")

    campaign_criterion = campaign_criterion_operation.create
    campaign_criterion.campaign = client.get_service("CampaignService").campaign_path(
        customer_id, campaign_id
    )
    campaign_criterion.location.geo_target_constant = client.get_service(
        "GeoTargetConstantService"
    ).geo_target_constant_path(location_id)
    campaign_criterion.bid_modifier = bid_modifier

    try:
        response = campaign_criterion_service.mutate_campaign_criteria(
            customer_id=customer_id,
            operations=[campaign_criterion_operation]
        )
        return {
            "success": True,
            "resource_name": response.results[0].resource_name,
            "message": f"Applied geo bid adjustment for location {location_id}: {bid_modifier:.0%}"
        }
    except GoogleAdsException as ex:
        return {
            "success": False,
            "error": str(ex),
            "message": f"Failed to apply geo bid adjustment"
        }


def apply_geo_exclusion(client, customer_id, campaign_id, location_id):
    """
    Exclude a geographic location from a campaign (negative location criterion).

    Args:
        client: Google Ads client
        customer_id: Customer ID
        campaign_id: Campaign ID
        location_id: Geographic location criterion ID to exclude
    """
    campaign_criterion_service = client.get_service("CampaignCriterionService")
    campaign_criterion_operation = client.get_type("CampaignCriterionOperation")

    campaign_criterion = campaign_criterion_operation.create
    campaign_criterion.campaign = client.get_service("CampaignService").campaign_path(
        customer_id, campaign_id
    )
    campaign_criterion.negative = True
    campaign_criterion.location.geo_target_constant = client.get_service(
        "GeoTargetConstantService"
    ).geo_target_constant_path(location_id)

    try:
        response = campaign_criterion_service.mutate_campaign_criteria(
            customer_id=customer_id,
            operations=[campaign_criterion_operation]
        )
        return {
            "success": True,
            "resource_name": response.results[0].resource_name,
            "message": f"Excluded location {location_id} from campaign {campaign_id}"
        }
    except GoogleAdsException as ex:
        return {
            "success": False,
            "error": str(ex),
            "message": f"Failed to exclude location {location_id}"
        }


def get_ad_group_id(client, customer_id, ad_group_name):
    """
    Get ad group ID from ad group name.

    Args:
        client: Google Ads client
        customer_id: Customer ID
        ad_group_name: Name of the ad group

    Returns:
        Ad group ID or None if not found
    """
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            ad_group.id,
            ad_group.name
        FROM ad_group
        WHERE ad_group.name = '{ad_group_name}'
        LIMIT 1
    """

    try:
        response = ga_service.search(customer_id=customer_id, query=query)

        for row in response:
            return str(row.ad_group.id)

        return None

    except GoogleAdsException as ex:
        print(f"Error fetching ad group '{ad_group_name}': {ex}")
        return None


def create_responsive_search_ad(client, customer_id, ad_group_name, headlines, descriptions, final_url):
    """
    Create a Responsive Search Ad (RSA).

    Args:
        client: Google Ads client
        customer_id: Customer ID
        ad_group_name: Name of the ad group to add the ad to
        headlines: List of headline strings (3-15 required)
        descriptions: List of description strings (2-4 required)
        final_url: Landing page URL

    Returns:
        Dict with success status and message
    """
    # Validate inputs
    if len(headlines) < 3 or len(headlines) > 15:
        return {
            "success": False,
            "message": f"Responsive Search Ads require 3-15 headlines. Provided: {len(headlines)}"
        }

    if len(descriptions) < 2 or len(descriptions) > 4:
        return {
            "success": False,
            "message": f"Responsive Search Ads require 2-4 descriptions. Provided: {len(descriptions)}"
        }

    # Get ad group ID
    ad_group_id = get_ad_group_id(client, customer_id, ad_group_name)
    if not ad_group_id:
        return {
            "success": False,
            "message": f"Ad group '{ad_group_name}' not found"
        }

    # Create ad group ad service and operation
    ad_group_ad_service = client.get_service("AdGroupAdService")
    ad_group_ad_operation = client.get_type("AdGroupAdOperation")

    # Build the ad
    ad_group_ad = ad_group_ad_operation.create
    ad_group_ad.ad_group = client.get_service("AdGroupService").ad_group_path(
        customer_id, ad_group_id
    )
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED

    # Set final URL
    ad_group_ad.ad.final_urls.append(final_url)

    # Create responsive search ad info
    responsive_search_ad = ad_group_ad.ad.responsive_search_ad

    # Add headlines (each as AdTextAsset)
    for headline_text in headlines:
        headline = client.get_type("AdTextAsset")
        headline.text = headline_text[:30]  # Max 30 characters
        responsive_search_ad.headlines.append(headline)

    # Add descriptions (each as AdTextAsset)
    for description_text in descriptions:
        description = client.get_type("AdTextAsset")
        description.text = description_text[:90]  # Max 90 characters
        responsive_search_ad.descriptions.append(description)

    # Execute
    try:
        response = ad_group_ad_service.mutate_ad_group_ads(
            customer_id=customer_id,
            operations=[ad_group_ad_operation]
        )
        return {
            "success": True,
            "resource_name": response.results[0].resource_name,
            "message": f"Created Responsive Search Ad in '{ad_group_name}' with {len(headlines)} headlines and {len(descriptions)} descriptions"
        }
    except GoogleAdsException as ex:
        return {
            "success": False,
            "error": str(ex),
            "message": f"Failed to create ad in '{ad_group_name}'"
        }


def add_sitelink_extensions(client, customer_id, campaign_ids, sitelinks):
    """
    Add sitelink extensions to campaigns.

    Args:
        client: Google Ads client
        customer_id: Customer ID
        campaign_ids: List of campaign IDs to apply sitelinks to
        sitelinks: List of dicts with 'text', 'description1', 'description2', 'final_url'

    Returns:
        List of results for each campaign
    """
    results = []

    for campaign_id in campaign_ids:
        asset_service = client.get_service("AssetService")
        campaign_asset_service = client.get_service("CampaignAssetService")

        operations = []

        for sitelink_data in sitelinks:
            # Create sitelink asset
            asset_operation = client.get_type("AssetOperation")
            asset = asset_operation.create
            asset.name = f"Sitelink: {sitelink_data['text']}"
            asset.type_ = client.enums.AssetTypeEnum.SITELINK

            sitelink_asset = asset.sitelink_asset
            sitelink_asset.link_text = sitelink_data['text'][:25]  # Max 25 chars
            sitelink_asset.description1 = sitelink_data.get('description1', '')[:35]  # Max 35 chars
            sitelink_asset.description2 = sitelink_data.get('description2', '')[:35]  # Max 35 chars

            asset.final_urls.append(sitelink_data['final_url'])

            try:
                # Create asset
                asset_response = asset_service.mutate_assets(
                    customer_id=customer_id,
                    operations=[asset_operation]
                )
                asset_resource_name = asset_response.results[0].resource_name

                # Link asset to campaign
                campaign_asset_operation = client.get_type("CampaignAssetOperation")
                campaign_asset = campaign_asset_operation.create
                campaign_asset.campaign = client.get_service("CampaignService").campaign_path(
                    customer_id, campaign_id
                )
                campaign_asset.asset = asset_resource_name
                campaign_asset.field_type = client.enums.AssetFieldTypeEnum.SITELINK

                campaign_asset_service.mutate_campaign_assets(
                    customer_id=customer_id,
                    operations=[campaign_asset_operation]
                )

                results.append({
                    "success": True,
                    "campaign_id": campaign_id,
                    "message": f"Added sitelink: {sitelink_data['text']}"
                })

            except GoogleAdsException as ex:
                results.append({
                    "success": False,
                    "campaign_id": campaign_id,
                    "error": str(ex),
                    "message": f"Failed to add sitelink: {sitelink_data['text']}"
                })

    return results


def add_callout_extensions(client, customer_id, campaign_ids, callouts):
    """
    Add callout extensions to campaigns.

    Args:
        client: Google Ads client
        customer_id: Customer ID
        campaign_ids: List of campaign IDs
        callouts: List of callout text strings

    Returns:
        List of results for each campaign
    """
    results = []

    for campaign_id in campaign_ids:
        asset_service = client.get_service("AssetService")
        campaign_asset_service = client.get_service("CampaignAssetService")

        for callout_text in callouts:
            # Create callout asset
            asset_operation = client.get_type("AssetOperation")
            asset = asset_operation.create
            asset.name = f"Callout: {callout_text}"
            asset.type_ = client.enums.AssetTypeEnum.CALLOUT

            callout_asset = asset.callout_asset
            callout_asset.callout_text = callout_text[:25]  # Max 25 chars

            try:
                # Create asset
                asset_response = asset_service.mutate_assets(
                    customer_id=customer_id,
                    operations=[asset_operation]
                )
                asset_resource_name = asset_response.results[0].resource_name

                # Link asset to campaign
                campaign_asset_operation = client.get_type("CampaignAssetOperation")
                campaign_asset = campaign_asset_operation.create
                campaign_asset.campaign = client.get_service("CampaignService").campaign_path(
                    customer_id, campaign_id
                )
                campaign_asset.asset = asset_resource_name
                campaign_asset.field_type = client.enums.AssetFieldTypeEnum.CALLOUT

                campaign_asset_service.mutate_campaign_assets(
                    customer_id=customer_id,
                    operations=[campaign_asset_operation]
                )

                results.append({
                    "success": True,
                    "campaign_id": campaign_id,
                    "message": f"Added callout: {callout_text}"
                })

            except GoogleAdsException as ex:
                results.append({
                    "success": False,
                    "campaign_id": campaign_id,
                    "error": str(ex),
                    "message": f"Failed to add callout: {callout_text}"
                })

    return results


def add_structured_snippet_extensions(client, customer_id, campaign_ids, header, values):
    """
    Add structured snippet extensions to campaigns.

    Args:
        client: Google Ads client
        customer_id: Customer ID
        campaign_ids: List of campaign IDs
        header: Structured snippet header (e.g., "Services", "Types", "Brands")
        values: List of value strings

    Returns:
        List of results for each campaign
    """
    results = []

    for campaign_id in campaign_ids:
        asset_service = client.get_service("AssetService")
        campaign_asset_service = client.get_service("CampaignAssetService")

        # Create structured snippet asset
        asset_operation = client.get_type("AssetOperation")
        asset = asset_operation.create
        asset.name = f"Snippet: {header}"
        asset.type_ = client.enums.AssetTypeEnum.STRUCTURED_SNIPPET

        snippet_asset = asset.structured_snippet_asset
        snippet_asset.header = header

        # Add values (max 25 chars each)
        for value in values:
            snippet_asset.values.append(value[:25])

        try:
            # Create asset
            asset_response = asset_service.mutate_assets(
                customer_id=customer_id,
                operations=[asset_operation]
            )
            asset_resource_name = asset_response.results[0].resource_name

            # Link asset to campaign
            campaign_asset_operation = client.get_type("CampaignAssetOperation")
            campaign_asset = campaign_asset_operation.create
            campaign_asset.campaign = client.get_service("CampaignService").campaign_path(
                customer_id, campaign_id
            )
            campaign_asset.asset = asset_resource_name
            campaign_asset.field_type = client.enums.AssetFieldTypeEnum.STRUCTURED_SNIPPET

            campaign_asset_service.mutate_campaign_assets(
                customer_id=customer_id,
                operations=[campaign_asset_operation]
            )

            results.append({
                "success": True,
                "campaign_id": campaign_id,
                "message": f"Added structured snippet: {header} with {len(values)} values"
            })

        except GoogleAdsException as ex:
            results.append({
                "success": False,
                "campaign_id": campaign_id,
                "error": str(ex),
                "message": f"Failed to add structured snippet: {header}"
            })

    return results


def apply_recommendations(customer_id, recommendations_file, approved_ids, dry_run=False):
    """
    Apply approved recommendations to Google Ads.

    Args:
        customer_id: Google Ads customer ID
        recommendations_file: Path to recommendations JSON file
        approved_ids: List of recommendation IDs to apply (1-based indices)
        dry_run: If True, show what would be done without applying
    """
    # Load recommendations
    with open(recommendations_file, 'r') as f:
        recommendations = json.load(f)

    # Initialize client (only if not dry run)
    client = None if dry_run else load_google_ads_client()

    results = []

    for idx in approved_ids:
        # Convert to 0-based index
        rec_index = idx - 1

        if rec_index < 0 or rec_index >= len(recommendations):
            results.append({
                "id": idx,
                "success": False,
                "message": f"Invalid recommendation ID: {idx}"
            })
            continue

        rec = recommendations[rec_index]
        rec_type = rec.get('type')
        action = rec.get('action')

        print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing recommendation #{idx}: {rec_type} - {action}")

        if dry_run:
            results.append({
                "id": idx,
                "type": rec_type,
                "action": action,
                "keyword": rec.get('keyword', 'N/A'),
                "message": "DRY RUN - No changes made",
                "would_execute": get_action_description(rec)
            })
            continue

        # Execute based on type and action
        if rec_type == 'keyword_action':
            if action == 'pause':
                result = pause_keyword(client, customer_id, rec.get('target'))
                result['id'] = idx
                result['keyword'] = rec.get('keyword')
                results.append(result)

            elif action == 'add_negative_keywords':
                # Use campaign_id from recommendation if available, otherwise look it up by ad group name
                campaign_id = rec.get('campaign_id')

                if not campaign_id:
                    # Fallback: Extract campaign ID from the target (ad group name)
                    campaign_id = get_campaign_from_ad_group(client, customer_id, rec.get('target'))

                if not campaign_id:
                    results.append({
                        "id": idx,
                        "success": False,
                        "message": f"Could not find campaign for ad group: {rec.get('target')}"
                    })
                    continue

                for neg_kw in rec.get('negative_keywords', []):
                    result = add_negative_keyword(client, customer_id, campaign_id, neg_kw, match_type="PHRASE")
                    result['id'] = idx
                    result['keyword'] = rec.get('keyword')
                    result['negative_keyword'] = neg_kw
                    results.append(result)

            elif action == 'change_to_phrase_match':
                result = change_keyword_match_type(client, customer_id, rec.get('target'), "PHRASE")
                result['id'] = idx
                result['keyword'] = rec.get('keyword')
                results.append(result)

        elif rec_type == 'bid_adjustment':
            result = adjust_keyword_bid(client, customer_id, rec.get('target'), rec.get('suggested_bid'))
            result['id'] = idx
            result['keyword'] = rec.get('keyword')
            results.append(result)

        elif rec_type == 'schedule_bid_adjustment':
            # Parse time slot and adjustment
            time_slot = rec.get('time_slot', '')
            suggested_adjustment = rec.get('suggested_adjustment', '')
            campaign_ids = rec.get('campaign_ids', [])

            if not campaign_ids:
                results.append({
                    "id": idx,
                    "success": False,
                    "message": "No campaign IDs specified for schedule adjustment"
                })
                continue

            # Extract hour (e.g., "23:00" -> 23) or day (e.g., "Friday")
            if ':' in time_slot:
                # Hourly adjustment
                hour = int(time_slot.split(':')[0])
                # Apply to all days of the week
                day_of_week = 'MONDAY'  # Default - applies to all days
                start_hour = hour
                end_hour = (hour + 1) % 24
            else:
                # Daily adjustment - not currently supported in this simplified version
                results.append({
                    "id": idx,
                    "success": False,
                    "message": "Daily schedule adjustments not yet implemented. Use hourly adjustments."
                })
                continue

            # Parse bid modifier (e.g., "+30%" -> 1.3, "-35%" -> 0.65)
            if suggested_adjustment.startswith('+'):
                modifier_pct = int(suggested_adjustment.strip('+%'))
                bid_modifier = 1.0 + (modifier_pct / 100.0)
            elif suggested_adjustment.startswith('-'):
                modifier_pct = int(suggested_adjustment.strip('-%'))
                bid_modifier = 1.0 - (modifier_pct / 100.0)
            else:
                results.append({
                    "id": idx,
                    "success": False,
                    "message": f"Invalid bid adjustment format: {suggested_adjustment}"
                })
                continue

            # Apply to all specified campaigns
            for campaign_id in campaign_ids:
                result = apply_schedule_bid_adjustment(
                    client, customer_id, campaign_id, day_of_week,
                    start_hour, end_hour, bid_modifier
                )
                result['id'] = idx
                result['campaign_id'] = campaign_id
                results.append(result)

        elif rec_type == 'geo_bid_adjustment':
            # Parse location and adjustment
            location = rec.get('location', '')
            suggested_adjustment = rec.get('suggested_adjustment', '')
            campaign_ids = rec.get('campaign_ids', [])

            if not campaign_ids:
                results.append({
                    "id": idx,
                    "success": False,
                    "message": "No campaign IDs specified for geo adjustment"
                })
                continue

            # Location ID mapping (Malaysia-focused)
            LOCATION_IDS = {
                "Malaysia": 2458,
                "Kuala Lumpur": 1015117,
                "Selangor": 1015118,
                "Johor": 1015134,
                "Penang": 1015128,
                "Perak": 1015119,
            }

            location_id = LOCATION_IDS.get(location)
            if not location_id:
                results.append({
                    "id": idx,
                    "success": False,
                    "message": f"Unknown location: {location}"
                })
                continue

            # Parse bid modifier
            if suggested_adjustment.startswith('+'):
                modifier_pct = int(suggested_adjustment.strip('+%'))
                bid_modifier = 1.0 + (modifier_pct / 100.0)
            elif suggested_adjustment.startswith('-'):
                modifier_pct = int(suggested_adjustment.strip('-%'))
                bid_modifier = 1.0 - (modifier_pct / 100.0)
            else:
                results.append({
                    "id": idx,
                    "success": False,
                    "message": f"Invalid bid adjustment format: {suggested_adjustment}"
                })
                continue

            # Apply to all specified campaigns
            for campaign_id in campaign_ids:
                result = apply_geo_bid_adjustment(
                    client, customer_id, campaign_id, location_id, bid_modifier
                )
                result['id'] = idx
                result['campaign_id'] = campaign_id
                result['location'] = location
                results.append(result)

        elif rec_type == 'ad_copy':
            # Create Responsive Search Ad
            ad_group_name = rec.get('ad_group_name')
            headline = rec.get('headline')
            description = rec.get('description')
            final_url = rec.get('final_url', 'https://www.yoursite.com')  # Default if not provided

            # Generate multiple variations for RSA
            # RSA requires 3-15 headlines and 2-4 descriptions
            headlines = [
                headline,
                headline.replace('Relief', 'Treatment'),
                headline.replace('Book Today', 'Free Consultation')
            ]

            descriptions = [
                description,
                f"{description} Book your appointment now."
            ]

            result = create_responsive_search_ad(
                client, customer_id, ad_group_name, headlines, descriptions, final_url
            )
            result['id'] = idx
            results.append(result)

        elif rec_type == 'geo_exclusion':
            # Exclude a geographic location from campaigns
            location = rec.get('location', '')
            campaign_ids = rec.get('campaign_ids', [])

            if not campaign_ids:
                results.append({
                    "id": idx,
                    "success": False,
                    "message": "No campaign IDs specified for geo exclusion"
                })
                continue

            # Location ID mapping (Malaysia-focused)
            LOCATION_IDS = {
                "Malaysia": 2458,
                "Kuala Lumpur": 1015117,
                "Selangor": 1015118,
                "Johor": 1015134,
                "Penang": 1015128,
                "Perak": 1015119,
            }

            location_id = LOCATION_IDS.get(location)
            if not location_id:
                results.append({
                    "id": idx,
                    "success": False,
                    "message": f"Unknown location for geo exclusion: {location}"
                })
                continue

            for campaign_id in campaign_ids:
                result = apply_geo_exclusion(
                    client, customer_id, campaign_id, location_id
                )
                result['id'] = idx
                result['campaign_id'] = campaign_id
                result['location'] = location
                results.append(result)

        elif rec_type == 'quality_improvement':
            # Handle quality score improvement - focus on ad extensions
            action = rec.get('action')
            issue = rec.get('issue')
            target = rec.get('target')

            if action == 'improve_quality_score' and issue == 'Expected CTR':
                # Add ad extensions to improve CTR
                # Get all campaign IDs from metrics
                campaign_ids = rec.get('campaign_ids', [])

                if not campaign_ids:
                    results.append({
                        "id": idx,
                        "success": False,
                        "message": "No campaign IDs available for ad extensions"
                    })
                    continue

                # Add callout extensions (simple, effective for CTR)
                callouts = [
                    "Expert Care",
                    "Fast Relief",
                    "Book Online 24/7",
                    "Same Day Appointments"
                ]

                callout_results = add_callout_extensions(client, customer_id, campaign_ids, callouts)

                # Add structured snippets
                snippet_results = add_structured_snippet_extensions(
                    client, customer_id, campaign_ids,
                    header="Services",
                    values=["Pain Relief", "Chiropractic Care", "Physiotherapy", "Massage Therapy"]
                )

                # Combine results
                for r in callout_results + snippet_results:
                    r['id'] = idx
                    results.append(r)

            elif action == 'improve_quality_score' and issue in ['Landing Page Experience', 'Ad Relevance']:
                # These require manual work (landing page creation or ad copy updates)
                results.append({
                    "id": idx,
                    "success": False,
                    "message": f"{issue} improvements require manual work. Suggested: {rec.get('suggested')}"
                })
            else:
                results.append({
                    "id": idx,
                    "success": False,
                    "message": f"Unknown quality improvement action: {action} for {issue}"
                })

        else:
            results.append({
                "id": idx,
                "success": False,
                "message": f"Unknown recommendation type: {rec_type}"
            })

    return results


def get_action_description(rec):
    """Get a human-readable description of what the action would do."""
    rec_type = rec.get('type')
    action = rec.get('action')

    if rec_type == 'keyword_action':
        if action == 'pause':
            return f"Pause keyword: {rec.get('keyword')}"
        elif action == 'add_negative_keywords':
            return f"Add negative keywords: {', '.join(rec.get('negative_keywords', []))}"
        elif action == 'change_to_phrase_match':
            return f"Change '{rec.get('keyword')}' to Phrase Match"
    elif rec_type == 'bid_adjustment':
        return f"Change bid from {rec.get('current_bid'):.2f} to {rec.get('suggested_bid'):.2f}"
    elif rec_type == 'schedule_bid_adjustment':
        return f"Apply {rec.get('suggested_adjustment')} bid adjustment for {rec.get('time_slot')}"
    elif rec_type == 'geo_bid_adjustment':
        return f"Apply {rec.get('suggested_adjustment')} bid adjustment for {rec.get('location')}"
    elif rec_type == 'geo_exclusion':
        return f"Exclude location '{rec.get('location')}' from campaigns"
    elif rec_type == 'ad_copy':
        return f"Create new ad copy for {rec.get('ad_group_name')}: {rec.get('headline')}"
    elif rec_type == 'quality_improvement':
        return f"Improve Quality Score for {rec.get('target')} - Fix: {rec.get('issue')}"

    return "Unknown action"


def main():
    parser = argparse.ArgumentParser(description="Apply approved Google Ads recommendations")
    parser.add_argument("--customer_id", required=True, help="Google Ads customer ID")
    parser.add_argument("--recommendations_file", required=True, help="Path to recommendations JSON")
    parser.add_argument("--approve", required=True, help="Comma-separated list of recommendation IDs to approve (e.g., 1,3,5)")
    parser.add_argument("--dry_run", action="store_true", help="Show what would be done without applying")

    args = parser.parse_args()

    # Parse approved IDs
    approved_ids = [int(x.strip()) for x in args.approve.split(',')]

    print(f"{'DRY RUN - ' if args.dry_run else ''}Applying recommendations: {approved_ids}")

    results = apply_recommendations(
        args.customer_id,
        args.recommendations_file,
        approved_ids,
        dry_run=args.dry_run
    )

    # Print results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    success_count = sum(1 for r in results if r.get('success', False))

    for result in results:
        status = "[SUCCESS]" if result.get('success') else "[FAILED]"
        print(f"\n#{result['id']}: {status}")
        print(f"  {result.get('message', 'No message')}")
        if 'would_execute' in result:
            print(f"  Would execute: {result['would_execute']}")

    print(f"\n{success_count}/{len(results)} recommendations applied successfully")


if __name__ == "__main__":
    main()
