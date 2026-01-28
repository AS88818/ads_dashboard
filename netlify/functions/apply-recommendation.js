/**
 * Netlify Function: Apply Google Ads Recommendation
 *
 * This serverless function applies recommendations to Google Ads
 * such as pausing keywords, adding negative keywords, or adjusting bids.
 *
 * Environment variables required:
 * - GOOGLE_ADS_DEVELOPER_TOKEN
 * - GOOGLE_ADS_CLIENT_ID
 * - GOOGLE_ADS_CLIENT_SECRET
 * - GOOGLE_ADS_REFRESH_TOKEN
 * - GOOGLE_ADS_LOGIN_CUSTOMER_ID
 * - GOOGLE_ADS_CUSTOMER_ID
 */

const { GoogleAdsApi, enums } = require('google-ads-api');

// Initialize Google Ads client
function getGoogleAdsClient() {
    return new GoogleAdsApi({
        client_id: process.env.GOOGLE_ADS_CLIENT_ID,
        client_secret: process.env.GOOGLE_ADS_CLIENT_SECRET,
        developer_token: process.env.GOOGLE_ADS_DEVELOPER_TOKEN
    });
}

function getCustomer(client) {
    return client.Customer({
        customer_id: process.env.GOOGLE_ADS_CUSTOMER_ID,
        login_customer_id: process.env.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
        refresh_token: process.env.GOOGLE_ADS_REFRESH_TOKEN
    });
}

// Parse the target_id to extract ad group and criterion IDs
// Format: "customers/7867388610/adGroupCriteria/156583250855~10596601"
function parseTargetId(targetId) {
    const match = targetId.match(/adGroupCriteria\/(\d+)~(\d+)/);
    if (match) {
        return {
            adGroupId: match[1],
            criterionId: match[2]
        };
    }
    return null;
}

// Pause a keyword
async function pauseKeyword(customer, targetId) {
    const parsed = parseTargetId(targetId);
    if (!parsed) {
        throw new Error(`Invalid target_id format: ${targetId}`);
    }

    const { adGroupId, criterionId } = parsed;
    const resourceName = `customers/${process.env.GOOGLE_ADS_CUSTOMER_ID}/adGroupCriteria/${adGroupId}~${criterionId}`;

    const operation = {
        update: {
            resource_name: resourceName,
            status: enums.AdGroupCriterionStatus.PAUSED
        },
        update_mask: {
            paths: ['status']
        }
    };

    const response = await customer.adGroupCriteria.update([operation]);
    return response;
}

// Enable a keyword
async function enableKeyword(customer, targetId) {
    const parsed = parseTargetId(targetId);
    if (!parsed) {
        throw new Error(`Invalid target_id format: ${targetId}`);
    }

    const { adGroupId, criterionId } = parsed;
    const resourceName = `customers/${process.env.GOOGLE_ADS_CUSTOMER_ID}/adGroupCriteria/${adGroupId}~${criterionId}`;

    const operation = {
        update: {
            resource_name: resourceName,
            status: enums.AdGroupCriterionStatus.ENABLED
        },
        update_mask: {
            paths: ['status']
        }
    };

    const response = await customer.adGroupCriteria.update([operation]);
    return response;
}

// Add a negative keyword to a campaign
async function addNegativeKeyword(customer, campaignId, keyword, matchType = 'PHRASE') {
    const matchTypeEnum = {
        'EXACT': enums.KeywordMatchType.EXACT,
        'PHRASE': enums.KeywordMatchType.PHRASE,
        'BROAD': enums.KeywordMatchType.BROAD
    };

    const operation = {
        create: {
            campaign: `customers/${process.env.GOOGLE_ADS_CUSTOMER_ID}/campaigns/${campaignId}`,
            keyword: {
                text: keyword,
                match_type: matchTypeEnum[matchType] || enums.KeywordMatchType.PHRASE
            },
            negative: true
        }
    };

    const response = await customer.campaignCriteria.create([operation]);
    return response;
}

// Main handler
exports.handler = async (event, context) => {
    // CORS headers
    const headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Content-Type': 'application/json'
    };

    // Handle preflight
    if (event.httpMethod === 'OPTIONS') {
        return { statusCode: 200, headers, body: '' };
    }

    // Only allow POST
    if (event.httpMethod !== 'POST') {
        return {
            statusCode: 405,
            headers,
            body: JSON.stringify({ error: 'Method not allowed' })
        };
    }

    // Check environment variables
    const requiredEnvVars = [
        'GOOGLE_ADS_DEVELOPER_TOKEN',
        'GOOGLE_ADS_CLIENT_ID',
        'GOOGLE_ADS_CLIENT_SECRET',
        'GOOGLE_ADS_REFRESH_TOKEN',
        'GOOGLE_ADS_LOGIN_CUSTOMER_ID',
        'GOOGLE_ADS_CUSTOMER_ID'
    ];

    const missingVars = requiredEnvVars.filter(v => !process.env[v]);
    if (missingVars.length > 0) {
        return {
            statusCode: 500,
            headers,
            body: JSON.stringify({
                error: 'Missing required environment variables',
                missing: missingVars
            })
        };
    }

    try {
        const body = JSON.parse(event.body || '{}');
        const { action_type, target_id, keyword, suggested_action, campaign_id, match_type } = body;

        if (!action_type) {
            return {
                statusCode: 400,
                headers,
                body: JSON.stringify({
                    error: 'Missing required field: action_type'
                })
            };
        }

        const client = getGoogleAdsClient();
        const customer = getCustomer(client);

        let result;
        let message;

        switch (action_type) {
            case 'keyword_action':
                if (suggested_action === 'PAUSED' || suggested_action?.includes('PAUSED')) {
                    if (!target_id) {
                        return {
                            statusCode: 400,
                            headers,
                            body: JSON.stringify({ error: 'Missing target_id for pause action' })
                        };
                    }
                    result = await pauseKeyword(customer, target_id);
                    message = `Successfully paused keyword "${keyword}"`;
                } else if (suggested_action === 'ENABLED') {
                    if (!target_id) {
                        return {
                            statusCode: 400,
                            headers,
                            body: JSON.stringify({ error: 'Missing target_id for enable action' })
                        };
                    }
                    result = await enableKeyword(customer, target_id);
                    message = `Successfully enabled keyword "${keyword}"`;
                } else {
                    // Default to pause for keyword actions
                    if (!target_id) {
                        return {
                            statusCode: 400,
                            headers,
                            body: JSON.stringify({ error: 'Missing target_id for keyword action' })
                        };
                    }
                    result = await pauseKeyword(customer, target_id);
                    message = `Successfully paused keyword "${keyword}"`;
                }
                break;

            case 'add_negative_keyword':
                if (!campaign_id || !keyword) {
                    return {
                        statusCode: 400,
                        headers,
                        body: JSON.stringify({
                            error: 'Adding negative keywords requires campaign_id and keyword'
                        })
                    };
                }
                result = await addNegativeKeyword(customer, campaign_id, keyword, match_type || 'PHRASE');
                message = `Successfully added "${keyword}" as negative keyword (${match_type || 'PHRASE'} match)`;
                break;

            case 'bid_adjustment':
                // Bid adjustments require user input for the new bid amount
                // Return instructions instead of making changes
                return {
                    statusCode: 200,
                    headers,
                    body: JSON.stringify({
                        success: false,
                        message: `Bid adjustments require you to specify the new bid amount. Please go to Google Ads UI to adjust the bid for "${keyword}".`,
                        manual_action_required: true,
                        google_ads_url: `https://ads.google.com/aw/keywords?campaignId=${campaign_id || ''}`
                    })
                };

            default:
                return {
                    statusCode: 400,
                    headers,
                    body: JSON.stringify({
                        error: `Unknown action type: ${action_type}`
                    })
                };
        }

        return {
            statusCode: 200,
            headers,
            body: JSON.stringify({
                success: true,
                message,
                result: result ? 'Applied' : null,
                timestamp: new Date().toISOString()
            })
        };

    } catch (error) {
        console.error('Error applying recommendation:', error);

        // Check for specific Google Ads API errors
        let errorMessage = error.message;
        if (error.errors && error.errors.length > 0) {
            errorMessage = error.errors.map(e => e.message || e.error_string).join('; ');
        }

        return {
            statusCode: 500,
            headers,
            body: JSON.stringify({
                error: 'Failed to apply recommendation',
                message: errorMessage,
                details: error.errors || null
            })
        };
    }
};
