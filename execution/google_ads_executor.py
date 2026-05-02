import os
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

def load_google_ads_client():
    """Load Google Ads API client from credentials."""
    login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "").strip()
    credentials = {
        "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": os.getenv("GOOGLE_ADS_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
        "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
        "use_proto_plus": True
    }
    if login_customer_id and len(login_customer_id) == 10 and login_customer_id.isdigit():
        credentials["login_customer_id"] = login_customer_id
    return GoogleAdsClient.load_from_dict(credentials)

def add_negative_keyword(customer_id, campaign_id, keyword, match_type="PHRASE"):
    """Execute adding a negative keyword to a campaign."""
    client = load_google_ads_client()
    campaign_criterion_service = client.get_service("CampaignCriterionService")
    
    # Create the campaign criterion
    campaign_criterion_operation = client.get_type("CampaignCriterionOperation")
    campaign_criterion = campaign_criterion_operation.create
    campaign_criterion.campaign = campaign_criterion_service.campaign_path(customer_id, campaign_id)
    campaign_criterion.negative = True
    
    # Set the keyword info
    match_type_enum = client.enums.KeywordMatchTypeEnum[match_type]
    campaign_criterion.keyword.text = keyword
    campaign_criterion.keyword.match_type = match_type_enum
    
    try:
        response = campaign_criterion_service.mutate_campaign_criteria(
            customer_id=customer_id, operations=[campaign_criterion_operation]
        )
        return {"status": "success", "resource_name": response.results[0].resource_name}
    except GoogleAdsException as ex:
        return {"status": "error", "message": f"Google Ads Error: {ex.error.code().name}"}

def pause_ad_group_criterion(customer_id, criterion_resource_name):
    """Execute pausing a specific keyword/criterion."""
    client = load_google_ads_client()
    agc_service = client.get_service("AdGroupCriterionService")
    
    operation = client.get_type("AdGroupCriterionOperation")
    criterion = operation.update
    criterion.resource_name = criterion_resource_name
    criterion.status = client.enums.AdGroupCriterionStatusEnum.PAUSED
    client.copy_from(operation.update_mask, client.get_helper().field_mask_helper_get_mask(None, criterion))
    
    try:
        response = agc_service.mutate_ad_group_criteria(
            customer_id=customer_id, operations=[operation]
        )
        return {"status": "success", "resource_name": response.results[0].resource_name}
    except GoogleAdsException as ex:
        return {"status": "error", "message": f"Google Ads Error: {ex.error.code().name}"}

def update_bid(customer_id, criterion_resource_name, suggested_bid):
    """Execute updating a CPC bid for a criterion."""
    client = load_google_ads_client()
    agc_service = client.get_service("AdGroupCriterionService")
    
    operation = client.get_type("AdGroupCriterionOperation")
    criterion = operation.update
    criterion.resource_name = criterion_resource_name
    criterion.cpc_bid_micros = int(suggested_bid * 1_000_000)
    client.copy_from(operation.update_mask, client.get_helper().field_mask_helper_get_mask(None, criterion))
    
    try:
        response = agc_service.mutate_ad_group_criteria(
            customer_id=customer_id, operations=[operation]
        )
        return {"status": "success", "resource_name": response.results[0].resource_name}
    except GoogleAdsException as ex:
        return {"status": "error", "message": f"Google Ads Error: {ex.error.code().name}"}
