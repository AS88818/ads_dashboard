#!/usr/bin/env python3
"""
Fetch Google Ads performance metrics for a specified customer and date range.

Usage:
    python fetch_google_ads_metrics.py --customer_id 1234567890 --start_date 2024-01-01 --end_date 2024-01-31

Output:
    JSON file in .tmp/ directory with all performance metrics
"""

import argparse
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

# Load environment variables
load_dotenv()


def load_google_ads_client():
    """Load Google Ads API client from credentials."""
    # Configuration can be loaded from google-ads.yaml or environment variables
    login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")

    # Remove dashes if present and validate
    login_customer_id = login_customer_id.replace("-", "").strip()

    credentials = {
        "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": os.getenv("GOOGLE_ADS_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
        "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
        "use_proto_plus": True
    }

    # Only add login_customer_id if it's valid (10 digits)
    if login_customer_id and len(login_customer_id) == 10 and login_customer_id.isdigit():
        credentials["login_customer_id"] = login_customer_id

    return GoogleAdsClient.load_from_dict(credentials)


def fetch_campaign_metrics(client, customer_id, start_date, end_date):
    """Fetch campaign-level performance metrics."""
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.cost_per_conversion,
            metrics.value_per_conversion,
            campaign.target_cpa.target_cpa_micros,
            campaign.target_roas.target_roas,
            campaign_budget.amount_micros
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND campaign.status != 'REMOVED'
        ORDER BY metrics.impressions DESC
    """

    campaigns = []
    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)

        for batch in response:
            for row in batch.results:
                campaign_data = {
                    "id": row.campaign.id,
                    "name": row.campaign.name,
                    "status": row.campaign.status.name,
                    "type": row.campaign.advertising_channel_type.name,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": row.metrics.ctr,
                    "avg_cpc": row.metrics.average_cpc / 1_000_000,  # Convert micros to currency
                    "cost": row.metrics.cost_micros / 1_000_000,
                    "conversions": row.metrics.conversions,
                    "conversion_value": row.metrics.conversions_value,
                    "cost_per_conversion": row.metrics.cost_per_conversion / 1_000_000 if row.metrics.cost_per_conversion else 0,
                    "value_per_conversion": row.metrics.value_per_conversion,
                    "roas": (row.metrics.conversions_value / (row.metrics.cost_micros / 1_000_000)) if row.metrics.cost_micros > 0 else 0,
                }
                campaigns.append(campaign_data)

    except GoogleAdsException as ex:
        print(f"Request failed with status {ex.error.code().name}")
        for error in ex.failure.errors:
            print(f"\tError: {error.message}")
        raise

    return campaigns


def fetch_adgroup_metrics(client, customer_id, start_date, end_date):
    """Fetch ad group-level performance metrics."""
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name,
            ad_group.status,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.cost_per_conversion
        FROM ad_group
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND ad_group.status != 'REMOVED'
        ORDER BY metrics.impressions DESC
    """

    ad_groups = []
    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)

        for batch in response:
            for row in batch.results:
                ad_group_data = {
                    "campaign_id": row.campaign.id,
                    "campaign_name": row.campaign.name,
                    "id": row.ad_group.id,
                    "name": row.ad_group.name,
                    "status": row.ad_group.status.name,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": row.metrics.ctr,
                    "avg_cpc": row.metrics.average_cpc / 1_000_000,
                    "cost": row.metrics.cost_micros / 1_000_000,
                    "conversions": row.metrics.conversions,
                    "conversion_value": row.metrics.conversions_value,
                    "cost_per_conversion": row.metrics.cost_per_conversion / 1_000_000 if row.metrics.cost_per_conversion else 0,
                    "roas": (row.metrics.conversions_value / (row.metrics.cost_micros / 1_000_000)) if row.metrics.cost_micros > 0 else 0,
                }
                ad_groups.append(ad_group_data)

    except GoogleAdsException as ex:
        print(f"Request failed with status {ex.error.code().name}")
        raise

    return ad_groups


def fetch_keyword_metrics(client, customer_id, start_date, end_date):
    """Fetch keyword-level performance metrics."""
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name,
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.quality_info.quality_score,
            ad_group_criterion.quality_info.creative_quality_score,
            ad_group_criterion.quality_info.post_click_quality_score,
            ad_group_criterion.quality_info.search_predicted_ctr,
            ad_group_criterion.criterion_id,
            ad_group_criterion.status,
            ad_group_criterion.cpc_bid_micros,
            ad_group_criterion.resource_name,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.cost_per_conversion
        FROM keyword_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND ad_group_criterion.status != 'REMOVED'
        ORDER BY metrics.impressions DESC
        LIMIT 1000
    """

    keywords = []
    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)

        for batch in response:
            for row in batch.results:
                keyword_data = {
                    "campaign_id": row.campaign.id,
                    "campaign_name": row.campaign.name,
                    "ad_group_id": row.ad_group.id,
                    "ad_group_name": row.ad_group.name,
                    "keyword_id": row.ad_group_criterion.criterion_id,
                    "keyword_text": row.ad_group_criterion.keyword.text,
                    "match_type": row.ad_group_criterion.keyword.match_type.name,
                    "status": row.ad_group_criterion.status.name,
                    "cpc_bid_micros": row.ad_group_criterion.cpc_bid_micros if hasattr(row.ad_group_criterion, 'cpc_bid_micros') else 0,
                    "resource_name": row.ad_group_criterion.resource_name,
                    "quality_score": row.ad_group_criterion.quality_info.quality_score,
                    "ad_relevance": row.ad_group_criterion.quality_info.creative_quality_score.name,
                    "landing_page_experience": row.ad_group_criterion.quality_info.post_click_quality_score.name,
                    "expected_ctr": row.ad_group_criterion.quality_info.search_predicted_ctr.name,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": row.metrics.ctr,
                    "avg_cpc": row.metrics.average_cpc / 1_000_000,
                    "cost": row.metrics.cost_micros / 1_000_000,
                    "conversions": row.metrics.conversions,
                    "conversion_value": row.metrics.conversions_value,
                    "cost_per_conversion": row.metrics.cost_per_conversion / 1_000_000 if row.metrics.cost_per_conversion else 0,
                    "roas": (row.metrics.conversions_value / (row.metrics.cost_micros / 1_000_000)) if row.metrics.cost_micros > 0 else 0,
                }
                keywords.append(keyword_data)

    except GoogleAdsException as ex:
        print(f"Request failed with status {ex.error.code().name}")
        raise

    return keywords


def fetch_ad_metrics(client, customer_id, start_date, end_date):
    """Fetch ad-level performance metrics for ad copy analysis."""
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name,
            ad_group_ad.ad.id,
            ad_group_ad.ad.type,
            ad_group_ad.ad.final_urls,
            ad_group_ad.ad.responsive_search_ad.headlines,
            ad_group_ad.ad.responsive_search_ad.descriptions,
            ad_group_ad.status,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.conversions,
            metrics.conversions_value,
            metrics.cost_micros
        FROM ad_group_ad
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND ad_group_ad.status != 'REMOVED'
            AND ad_group_ad.ad.type = 'RESPONSIVE_SEARCH_AD'
        ORDER BY metrics.impressions DESC
        LIMIT 500
    """

    ads = []
    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)

        for batch in response:
            for row in batch.results:
                # Extract headlines and descriptions
                headlines = [h.text for h in row.ad_group_ad.ad.responsive_search_ad.headlines]
                descriptions = [d.text for d in row.ad_group_ad.ad.responsive_search_ad.descriptions]

                # Extract final URLs (landing pages)
                final_urls = list(row.ad_group_ad.ad.final_urls) if row.ad_group_ad.ad.final_urls else []

                ad_data = {
                    "campaign_id": row.campaign.id,
                    "campaign_name": row.campaign.name,
                    "ad_group_id": row.ad_group.id,
                    "ad_group_name": row.ad_group.name,
                    "ad_id": row.ad_group_ad.ad.id,
                    "ad_type": row.ad_group_ad.ad.type_.name,
                    "status": row.ad_group_ad.status.name,
                    "final_urls": final_urls,
                    "headlines": headlines,
                    "descriptions": descriptions,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": row.metrics.ctr,
                    "conversions": row.metrics.conversions,
                    "conversion_value": row.metrics.conversions_value,
                    "cost": row.metrics.cost_micros / 1_000_000,
                    "roas": (row.metrics.conversions_value / (row.metrics.cost_micros / 1_000_000)) if row.metrics.cost_micros > 0 else 0,
                }
                ads.append(ad_data)

    except GoogleAdsException as ex:
        print(f"Request failed with status {ex.error.code().name}")
        raise

    return ads


def fetch_search_query_report(client, customer_id, start_date, end_date):
    """Fetch search query performance report - what users actually searched for."""
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name,
            segments.search_term_match_type,
            search_term_view.search_term,
            search_term_view.status,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM search_term_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
        LIMIT 500
    """

    search_queries = []
    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)

        for batch in response:
            for row in batch.results:
                query_data = {
                    "campaign_id": row.campaign.id,
                    "campaign_name": row.campaign.name,
                    "ad_group_id": row.ad_group.id,
                    "ad_group_name": row.ad_group.name,
                    "search_term": row.search_term_view.search_term,
                    "match_type": row.segments.search_term_match_type.name,
                    "status": row.search_term_view.status.name,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": row.metrics.ctr,
                    "avg_cpc": row.metrics.average_cpc / 1_000_000,
                    "cost": row.metrics.cost_micros / 1_000_000,
                    "conversions": row.metrics.conversions,
                    "conversion_value": row.metrics.conversions_value,
                }
                search_queries.append(query_data)

    except GoogleAdsException as ex:
        print(f"Request failed with status {ex.error.code().name}")
        # Search query report might not be available for all accounts
        print("Note: Search query report not available or no data")
        return []

    return search_queries


def fetch_geographic_metrics(client, customer_id, start_date, end_date):
    """Fetch geographic performance report with city-level detail using user_location_view."""
    ga_service = client.get_service("GoogleAdsService")
    geo_target_service = client.get_service("GeoTargetConstantService")

    # Use user_location_view for more detailed location data (cities, regions)
    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            user_location_view.country_criterion_id,
            user_location_view.targeting_location,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM user_location_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND metrics.impressions > 0
        ORDER BY metrics.clicks DESC
        LIMIT 100
    """

    geo_data = []
    location_cache = {}  # Cache for location names

    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)

        for batch in response:
            for row in batch.results:
                # Get the targeting location resource name (contains city/region info)
                targeting_location = None
                location_name = None

                if hasattr(row.user_location_view, 'targeting_location'):
                    tl = row.user_location_view.targeting_location
                    # targeting_location is a resource name string like "geoTargetConstants/12345"
                    if tl and isinstance(tl, str) and '/' in tl:
                        targeting_location = tl
                        location_id = targeting_location.split('/')[-1]
                        # Try to get location name from cache or API
                        if location_id in location_cache:
                            location_name = location_cache[location_id]
                        else:
                            try:
                                # Fetch the geo target constant to get the location name
                                geo_target = geo_target_service.get_geo_target_constant(
                                    resource_name=targeting_location
                                )
                                location_name = geo_target.name
                                location_cache[location_id] = location_name
                            except Exception:
                                location_name = f"Location {location_id}"
                                location_cache[location_id] = location_name

                location_data = {
                    "campaign_id": row.campaign.id,
                    "campaign_name": row.campaign.name,
                    "country_criterion_id": row.user_location_view.country_criterion_id if hasattr(row.user_location_view, 'country_criterion_id') else None,
                    "targeting_location": targeting_location,
                    "location_name": location_name,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": row.metrics.ctr,
                    "avg_cpc": row.metrics.average_cpc / 1_000_000,
                    "cost": row.metrics.cost_micros / 1_000_000,
                    "conversions": row.metrics.conversions,
                    "conversion_value": row.metrics.conversions_value,
                    "cost_per_conversion": (row.metrics.cost_micros / 1_000_000 / row.metrics.conversions) if row.metrics.conversions > 0 else 0,
                }
                geo_data.append(location_data)

    except GoogleAdsException as ex:
        print(f"Geographic request failed with status {ex.error.code().name}")
        # Fall back to geographic_view if user_location_view fails
        return fetch_geographic_metrics_fallback(client, customer_id, start_date, end_date)

    return geo_data


def fetch_geographic_metrics_fallback(client, customer_id, start_date, end_date):
    """Fallback to basic geographic_view if user_location_view fails."""
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            geographic_view.country_criterion_id,
            geographic_view.location_type,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM geographic_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 100
    """

    geo_data = []
    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)

        for batch in response:
            for row in batch.results:
                location_data = {
                    "campaign_id": row.campaign.id,
                    "campaign_name": row.campaign.name,
                    "country_criterion_id": row.geographic_view.country_criterion_id if hasattr(row.geographic_view, 'country_criterion_id') else None,
                    "location_type": row.geographic_view.location_type.name if hasattr(row.geographic_view, 'location_type') else "UNKNOWN",
                    "location_name": None,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": row.metrics.ctr,
                    "avg_cpc": row.metrics.average_cpc / 1_000_000,
                    "cost": row.metrics.cost_micros / 1_000_000,
                    "conversions": row.metrics.conversions,
                    "conversion_value": row.metrics.conversions_value,
                    "cost_per_conversion": (row.metrics.cost_micros / 1_000_000 / row.metrics.conversions) if row.metrics.conversions > 0 else 0,
                }
                geo_data.append(location_data)

    except GoogleAdsException as ex:
        print(f"Geographic fallback failed: {ex.error.code().name}")
        return []

    return geo_data


def fetch_time_segmented_metrics(client, customer_id, start_date, end_date):
    """Fetch performance metrics segmented by hour of day and day of week."""
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            segments.hour,
            segments.day_of_week,
            segments.date,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND metrics.impressions > 0
        ORDER BY segments.date DESC, segments.hour ASC
    """

    time_data = []
    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)

        for batch in response:
            for row in batch.results:
                time_record = {
                    "date": row.segments.date,
                    "hour": row.segments.hour,
                    "day_of_week": row.segments.day_of_week.name if hasattr(row.segments, 'day_of_week') else "UNKNOWN",
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": row.metrics.ctr,
                    "avg_cpc": row.metrics.average_cpc / 1_000_000,
                    "cost": row.metrics.cost_micros / 1_000_000,
                    "conversions": row.metrics.conversions,
                    "conversion_value": row.metrics.conversions_value,
                    "cost_per_conversion": (row.metrics.cost_micros / 1_000_000 / row.metrics.conversions) if row.metrics.conversions > 0 else 0,
                }
                time_data.append(time_record)

    except GoogleAdsException as ex:
        print(f"Request failed with status {ex.error.code().name}")
        print("Note: Time-segmented data not available or no data")
        return []

    return time_data


def main():
    parser = argparse.ArgumentParser(description="Fetch Google Ads performance metrics")
    parser.add_argument("--customer_id", required=True, help="Google Ads customer ID (without dashes)")
    parser.add_argument("--start_date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end_date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output_dir", default=".tmp", help="Output directory for JSON file")

    args = parser.parse_args()

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    # Initialize Google Ads client
    print("Initializing Google Ads API client...")
    client = load_google_ads_client()

    # Fetch metrics at all levels
    print(f"Fetching metrics for customer {args.customer_id} from {args.start_date} to {args.end_date}...")

    print("  - Fetching campaign metrics...")
    campaigns = fetch_campaign_metrics(client, args.customer_id, args.start_date, args.end_date)

    print("  - Fetching ad group metrics...")
    ad_groups = fetch_adgroup_metrics(client, args.customer_id, args.start_date, args.end_date)

    print("  - Fetching keyword metrics...")
    keywords = fetch_keyword_metrics(client, args.customer_id, args.start_date, args.end_date)

    print("  - Fetching ad metrics...")
    ads = fetch_ad_metrics(client, args.customer_id, args.start_date, args.end_date)

    print("  - Fetching search query report...")
    search_queries = fetch_search_query_report(client, args.customer_id, args.start_date, args.end_date)

    print("  - Fetching geographic performance...")
    geo_performance = fetch_geographic_metrics(client, args.customer_id, args.start_date, args.end_date)

    print("  - Fetching time-segmented performance...")
    time_performance = fetch_time_segmented_metrics(client, args.customer_id, args.start_date, args.end_date)

    # Compile all data
    metrics_data = {
        "customer_id": args.customer_id,
        "date_range": {
            "start_date": args.start_date,
            "end_date": args.end_date
        },
        "fetched_at": datetime.now().isoformat(),
        "campaigns": campaigns,
        "ad_groups": ad_groups,
        "keywords": keywords,
        "ads": ads,
        "search_queries": search_queries,
        "geo_performance": geo_performance,
        "time_performance": time_performance,
        "summary": {
            "total_campaigns": len(campaigns),
            "total_ad_groups": len(ad_groups),
            "total_keywords": len(keywords),
            "total_ads": len(ads),
            "total_search_queries": len(search_queries),
            "total_geo_locations": len(geo_performance),
            "total_time_segments": len(time_performance),
            "total_impressions": sum(c["impressions"] for c in campaigns),
            "total_clicks": sum(c["clicks"] for c in campaigns),
            "total_cost": sum(c["cost"] for c in campaigns),
            "total_conversions": sum(c["conversions"] for c in campaigns),
            "total_conversion_value": sum(c["conversion_value"] for c in campaigns),
        }
    }

    # Calculate overall ROAS
    if metrics_data["summary"]["total_cost"] > 0:
        metrics_data["summary"]["overall_roas"] = (
            metrics_data["summary"]["total_conversion_value"] /
            metrics_data["summary"]["total_cost"]
        )
    else:
        metrics_data["summary"]["overall_roas"] = 0

    # Save to JSON file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(
        args.output_dir,
        f"google_ads_metrics_{args.customer_id}_{timestamp}.json"
    )

    with open(output_file, 'w') as f:
        json.dump(metrics_data, f, indent=2)

    print(f"\n[OK] Metrics saved to: {output_file}")
    print(f"\nSummary:")
    print(f"  Campaigns: {metrics_data['summary']['total_campaigns']}")
    print(f"  Ad Groups: {metrics_data['summary']['total_ad_groups']}")
    print(f"  Keywords: {metrics_data['summary']['total_keywords']}")
    print(f"  Ads: {metrics_data['summary']['total_ads']}")
    print(f"  Total Impressions: {metrics_data['summary']['total_impressions']:,}")
    print(f"  Total Clicks: {metrics_data['summary']['total_clicks']:,}")
    print(f"  Total Cost: ${metrics_data['summary']['total_cost']:,.2f}")
    print(f"  Total Conversions: {metrics_data['summary']['total_conversions']:.2f}")
    print(f"  Overall ROAS: {metrics_data['summary']['overall_roas']:.2f}x")

    # Return output file path for orchestration
    return output_file


if __name__ == "__main__":
    main()
