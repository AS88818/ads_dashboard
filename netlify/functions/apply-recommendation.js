/**
 * Netlify Function: Apply Google Ads Recommendation
 *
 * This serverless function applies recommendations to Google Ads
 * such as pausing keywords, adding negative keywords, or adjusting bids.
 *
 * Uses REST API instead of gRPC to avoid serverless compatibility issues.
 *
 * Environment variables required:
 * - GOOGLE_ADS_DEVELOPER_TOKEN
 * - GOOGLE_ADS_CLIENT_ID
 * - GOOGLE_ADS_CLIENT_SECRET
 * - GOOGLE_ADS_REFRESH_TOKEN
 * - GOOGLE_ADS_LOGIN_CUSTOMER_ID
 * - GOOGLE_ADS_CUSTOMER_ID
 */

// Get OAuth2 access token using refresh token
async function getAccessToken() {
    const tokenUrl = 'https://oauth2.googleapis.com/token';

    const params = new URLSearchParams({
        client_id: process.env.GOOGLE_ADS_CLIENT_ID,
        client_secret: process.env.GOOGLE_ADS_CLIENT_SECRET,
        refresh_token: process.env.GOOGLE_ADS_REFRESH_TOKEN,
        grant_type: 'refresh_token'
    });

    const response = await fetch(tokenUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: params.toString()
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`Failed to get access token: ${JSON.stringify(errorData)}`);
    }

    const data = await response.json();
    return data.access_token;
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

// Execute a mutate operation via REST API
async function executeMutate(accessToken, customerId, resourceType, operations) {
    const loginCustomerId = process.env.GOOGLE_ADS_LOGIN_CUSTOMER_ID;
    const developerToken = process.env.GOOGLE_ADS_DEVELOPER_TOKEN;

    // Google Ads REST API v18 endpoint
    const url = `https://googleads.googleapis.com/v18/customers/${customerId}/${resourceType}:mutate`;

    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${accessToken}`,
            'developer-token': developerToken,
            'login-customer-id': loginCustomerId,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ operations })
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Google Ads API error: ${response.status} - ${errorText}`);
    }

    return await response.json();
}

// Pause a keyword
async function pauseKeyword(accessToken, customerId, targetId) {
    const parsed = parseTargetId(targetId);
    if (!parsed) {
        throw new Error(`Invalid target_id format: ${targetId}`);
    }

    const { adGroupId, criterionId } = parsed;
    const resourceName = `customers/${customerId}/adGroupCriteria/${adGroupId}~${criterionId}`;

    const operations = [{
        updateMask: 'status',
        update: {
            resourceName: resourceName,
            status: 'PAUSED'
        }
    }];

    return await executeMutate(accessToken, customerId, 'adGroupCriteria', operations);
}

// Enable a keyword
async function enableKeyword(accessToken, customerId, targetId) {
    const parsed = parseTargetId(targetId);
    if (!parsed) {
        throw new Error(`Invalid target_id format: ${targetId}`);
    }

    const { adGroupId, criterionId } = parsed;
    const resourceName = `customers/${customerId}/adGroupCriteria/${adGroupId}~${criterionId}`;

    const operations = [{
        updateMask: 'status',
        update: {
            resourceName: resourceName,
            status: 'ENABLED'
        }
    }];

    return await executeMutate(accessToken, customerId, 'adGroupCriteria', operations);
}

// Add a negative keyword to a campaign
async function addNegativeKeyword(accessToken, customerId, campaignId, keyword, matchType = 'PHRASE') {
    const operations = [{
        create: {
            campaign: `customers/${customerId}/campaigns/${campaignId}`,
            keyword: {
                text: keyword,
                matchType: matchType
            },
            negative: true
        }
    }];

    return await executeMutate(accessToken, customerId, 'campaignCriteria', operations);
}

// Adjust keyword bid
async function adjustKeywordBid(accessToken, customerId, targetId, newBid) {
    const parsed = parseTargetId(targetId);
    if (!parsed) {
        throw new Error(`Invalid target_id format: ${targetId}`);
    }

    const { adGroupId, criterionId } = parsed;
    const resourceName = `customers/${customerId}/adGroupCriteria/${adGroupId}~${criterionId}`;

    // Convert bid to micros (1 currency unit = 1,000,000 micros)
    // Round to nearest 0.01 (10,000 micros) to meet billable unit requirement
    const bidMicros = Math.round(newBid * 1000000 / 10000) * 10000;

    const operations = [{
        updateMask: 'cpcBidMicros',
        update: {
            resourceName: resourceName,
            cpcBidMicros: bidMicros.toString()
        }
    }];

    return await executeMutate(accessToken, customerId, 'adGroupCriteria', operations);
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
        const { action_type, target_id, keyword, suggested_action, campaign_id, match_type, new_bid } = body;

        if (!action_type) {
            return {
                statusCode: 400,
                headers,
                body: JSON.stringify({
                    error: 'Missing required field: action_type'
                })
            };
        }

        const customerId = process.env.GOOGLE_ADS_CUSTOMER_ID;

        // Get fresh access token
        console.log('Getting access token...');
        const accessToken = await getAccessToken();
        console.log('Access token obtained');

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
                    result = await pauseKeyword(accessToken, customerId, target_id);
                    message = `Successfully paused keyword "${keyword}"`;
                } else if (suggested_action === 'ENABLED') {
                    if (!target_id) {
                        return {
                            statusCode: 400,
                            headers,
                            body: JSON.stringify({ error: 'Missing target_id for enable action' })
                        };
                    }
                    result = await enableKeyword(accessToken, customerId, target_id);
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
                    result = await pauseKeyword(accessToken, customerId, target_id);
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
                result = await addNegativeKeyword(accessToken, customerId, campaign_id, keyword, match_type || 'PHRASE');
                message = `Successfully added "${keyword}" as negative keyword (${match_type || 'PHRASE'} match)`;
                break;

            case 'bid_adjustment':
                // Bid adjustments require target_id and new_bid
                if (!target_id) {
                    return {
                        statusCode: 400,
                        headers,
                        body: JSON.stringify({ error: 'Missing target_id for bid adjustment' })
                    };
                }
                if (!new_bid || isNaN(parseFloat(new_bid))) {
                    return {
                        statusCode: 400,
                        headers,
                        body: JSON.stringify({
                            error: 'Missing or invalid new_bid amount',
                            requires_input: true,
                            input_type: 'bid_amount'
                        })
                    };
                }
                const bidAmount = parseFloat(new_bid);
                if (bidAmount <= 0) {
                    return {
                        statusCode: 400,
                        headers,
                        body: JSON.stringify({ error: 'Bid amount must be greater than 0' })
                    };
                }
                result = await adjustKeywordBid(accessToken, customerId, target_id, bidAmount);
                message = `Successfully adjusted bid for "${keyword}" to RM ${bidAmount.toFixed(2)}`;
                break;

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

        return {
            statusCode: 500,
            headers,
            body: JSON.stringify({
                error: 'Failed to apply recommendation',
                message: errorMessage
            })
        };
    }
};
