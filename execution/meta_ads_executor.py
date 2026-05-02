import os
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad

def init_facebook_api():
    """Initialize the Facebook Ads API from environment variables."""
    app_id = os.getenv('FACEBOOK_APP_ID')
    app_secret = os.getenv('FACEBOOK_APP_SECRET')
    access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
    if not access_token:
        raise Exception("FACEBOOK_ACCESS_TOKEN not set")
    FacebookAdsApi.init(app_id or '', app_secret or '', access_token)

def pause_campaign(campaign_id):
    """Pause a Meta Ads campaign."""
    init_facebook_api()
    campaign = Campaign(campaign_id)
    campaign.remote_update(params={
        'status': Campaign.Status.paused,
    })
    return {"status": "success", "id": campaign_id}

def pause_ad_set(ad_set_id):
    """Pause a Meta Ads ad set."""
    init_facebook_api()
    adset = AdSet(ad_set_id)
    adset.remote_update(params={
        'status': AdSet.Status.paused,
    })
    return {"status": "success", "id": ad_set_id}

def update_budget(campaign_id, suggested_budget):
    """Update the daily budget for a Meta Ads campaign."""
    init_facebook_api()
    campaign = Campaign(campaign_id)
    # Meta budgets are in cents (integer)
    budget_cents = int(float(suggested_budget) * 100)
    campaign.remote_update(params={
        'daily_budget': budget_cents,
    })
    return {"status": "success", "id": campaign_id}

def update_ad_set_budget(ad_set_id, suggested_budget):
    """Update the daily budget for a Meta Ads ad set."""
    init_facebook_api()
    adset = AdSet(ad_set_id)
    budget_cents = int(float(suggested_budget) * 100)
    adset.remote_update(params={
        'daily_budget': budget_cents,
    })
    return {"status": "success", "id": ad_set_id}
