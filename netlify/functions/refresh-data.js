/**
 * Netlify Function: Refresh Google Ads Data
 *
 * This serverless function fetches data from Google Ads REST API
 * and generates insights for the dashboard.
 *
 * Uses REST API instead of gRPC to avoid serverless compatibility issues.
 *
 * Environment variables required:
 * - GOOGLE_ADS_DEVELOPER_TOKEN
 * - GOOGLE_ADS_CLIENT_ID
 * - GOOGLE_ADS_CLIENT_SECRET
 * - GOOGLE_ADS_REFRESH_TOKEN
 * - GOOGLE_ADS_LOGIN_CUSTOMER_ID
 * - GOOGLE_ADS_CUSTOMER_ID (e.g., 7867388610 for YCK)
 */

// Helper functions
function formatDate(date) {
    return date.toISOString().split('T')[0];
}

function getDateRange(days = 30) {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);
    return {
        start: formatDate(startDate),
        end: formatDate(endDate)
    };
}

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

// Execute Google Ads GAQL query via REST API
async function executeGaqlQuery(accessToken, customerId, query) {
    const loginCustomerId = process.env.GOOGLE_ADS_LOGIN_CUSTOMER_ID;
    const developerToken = process.env.GOOGLE_ADS_DEVELOPER_TOKEN;

    // Google Ads REST API v18 endpoint
    const url = `https://googleads.googleapis.com/v18/customers/${customerId}/googleAds:searchStream`;

    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${accessToken}`,
            'developer-token': developerToken,
            'login-customer-id': loginCustomerId,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query })
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Google Ads API error: ${response.status} - ${errorText}`);
    }

    const data = await response.json();

    // searchStream returns an array of result batches
    const results = [];
    if (Array.isArray(data)) {
        for (const batch of data) {
            if (batch.results) {
                results.push(...batch.results);
            }
        }
    }

    return results;
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

    // Only allow POST requests
    if (event.httpMethod !== 'POST') {
        return {
            statusCode: 405,
            headers,
            body: JSON.stringify({ error: 'Method not allowed' })
        };
    }

    // Check for required environment variables
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
        const customerId = process.env.GOOGLE_ADS_CUSTOMER_ID;

        // Get fresh access token
        console.log('Getting access token...');
        const accessToken = await getAccessToken();
        console.log('Access token obtained');

        const dateRange = getDateRange(30);

        // Fetch campaign data
        console.log('Fetching campaign data...');
        const campaignQuery = `
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                metrics.cost_micros,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.ctr,
                metrics.average_cpc
            FROM campaign
            WHERE segments.date BETWEEN '${dateRange.start}' AND '${dateRange.end}'
            ORDER BY metrics.cost_micros DESC
            LIMIT 20
        `;

        const campaignResults = await executeGaqlQuery(accessToken, customerId, campaignQuery);
        console.log(`Fetched ${campaignResults.length} campaigns`);

        // Fetch keyword data
        console.log('Fetching keyword data...');
        const keywordQuery = `
            SELECT
                ad_group_criterion.keyword.text,
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.average_cpc,
                ad_group_criterion.quality_info.quality_score
            FROM keyword_view
            WHERE segments.date BETWEEN '${dateRange.start}' AND '${dateRange.end}'
                AND ad_group_criterion.status = 'ENABLED'
            ORDER BY metrics.impressions DESC
            LIMIT 20
        `;

        const keywordResults = await executeGaqlQuery(accessToken, customerId, keywordQuery);
        console.log(`Fetched ${keywordResults.length} keywords`);

        // Fetch search queries
        console.log('Fetching search queries...');
        const searchQuerySQL = `
            SELECT
                search_term_view.search_term,
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions
            FROM search_term_view
            WHERE segments.date BETWEEN '${dateRange.start}' AND '${dateRange.end}'
            ORDER BY metrics.clicks DESC
            LIMIT 15
        `;

        let searchQueryResults = [];
        try {
            searchQueryResults = await executeGaqlQuery(accessToken, customerId, searchQuerySQL);
            console.log(`Fetched ${searchQueryResults.length} search queries`);
        } catch (err) {
            console.log('Could not fetch search queries:', err.message);
        }

        // Fetch geographic data
        console.log('Fetching geographic data...');
        const geoQuery = `
            SELECT
                geographic_view.country_criterion_id,
                geographic_view.location_type,
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.cost_micros,
                metrics.conversions
            FROM geographic_view
            WHERE segments.date BETWEEN '${dateRange.start}' AND '${dateRange.end}'
            ORDER BY metrics.clicks DESC
            LIMIT 15
        `;

        let geoResults = [];
        try {
            geoResults = await executeGaqlQuery(accessToken, customerId, geoQuery);
            console.log(`Fetched ${geoResults.length} geo records`);
        } catch (err) {
            console.log('Could not fetch geographic data:', err.message);
        }

        // Process campaign data
        const campaigns = campaignResults.map(row => ({
            id: row.campaign?.id || null,
            name: row.campaign?.name || 'Unknown',
            status: row.campaign?.status || 'UNKNOWN',
            spend: (row.metrics?.costMicros || 0) / 1000000,
            impressions: parseInt(row.metrics?.impressions || 0),
            clicks: parseInt(row.metrics?.clicks || 0),
            ctr: parseFloat(row.metrics?.ctr || 0) * 100,
            conversions: parseFloat(row.metrics?.conversions || 0),
            cpa: row.metrics?.conversions > 0
                ? (row.metrics?.costMicros / 1000000) / row.metrics.conversions
                : 0
        }));

        // Create campaign ID map for later use
        const campaignIdMap = {};
        campaigns.forEach(c => {
            campaignIdMap[c.name] = c.id;
        });

        // Process keyword data
        const keywords = keywordResults.map(row => ({
            keyword: row.adGroupCriterion?.keyword?.text || 'Unknown',
            campaign: row.campaign?.name || '-',
            impressions: parseInt(row.metrics?.impressions || 0),
            clicks: parseInt(row.metrics?.clicks || 0),
            ctr: parseFloat(row.metrics?.ctr || 0) * 100,
            avg_cpc: (row.metrics?.averageCpc || 0) / 1000000,
            quality_score: row.adGroupCriterion?.qualityInfo?.qualityScore || null
        }));

        // Process search queries
        const searchQueries = searchQueryResults.map(row => ({
            query: row.searchTermView?.searchTerm || '',
            campaign: row.campaign?.name || '',
            impressions: parseInt(row.metrics?.impressions || 0),
            clicks: parseInt(row.metrics?.clicks || 0),
            cost: (row.metrics?.costMicros || 0) / 1000000,
            conversions: parseFloat(row.metrics?.conversions || 0)
        }));

        // Process geographic data
        const geoPerformance = geoResults.map(row => ({
            location_name: `Location ${row.geographicView?.countryCriterionId || 'Unknown'}`,
            country_criterion_id: row.geographicView?.countryCriterionId || null,
            location_type: row.geographicView?.locationType || '',
            campaign_name: row.campaign?.name || '',
            impressions: parseInt(row.metrics?.impressions || 0),
            clicks: parseInt(row.metrics?.clicks || 0),
            ctr: parseFloat(row.metrics?.ctr || 0),
            cost: (row.metrics?.costMicros || 0) / 1000000,
            conversions: parseFloat(row.metrics?.conversions || 0)
        }));

        // Calculate summary metrics
        const summary = {
            total_spend: campaigns.reduce((sum, c) => sum + c.spend, 0),
            total_impressions: campaigns.reduce((sum, c) => sum + c.impressions, 0),
            total_clicks: campaigns.reduce((sum, c) => sum + c.clicks, 0),
            total_conversions: campaigns.reduce((sum, c) => sum + c.conversions, 0),
            cost_per_conversion: 0,
            avg_ctr: 0,
            avg_quality_score: 0
        };

        if (summary.total_conversions > 0) {
            summary.cost_per_conversion = summary.total_spend / summary.total_conversions;
        }

        if (summary.total_impressions > 0) {
            summary.avg_ctr = (summary.total_clicks / summary.total_impressions) * 100;
        }

        const validQualityScores = keywords.filter(k => k.quality_score && k.quality_score > 0);
        if (validQualityScores.length > 0) {
            summary.avg_quality_score = validQualityScores.reduce((sum, k) => sum + k.quality_score, 0) / validQualityScores.length;
        }

        // Generate AI-style insights
        const insights = generateInsights(summary, campaigns, keywords, searchQueries);
        const recommendations = generateRecommendations(summary, campaigns, keywords, searchQueries, campaignIdMap);

        // Build final response
        const data = {
            customer_id: customerId,
            account_name: 'YCK Chiropractic',
            generated_at: new Date().toISOString(),
            date_range: dateRange,
            summary,
            trends: {
                spend_change: 0,
                conversions_change: 0,
                cpa_change: 0,
                quality_score_change: 0
            },
            campaigns,
            keywords,
            search_queries: searchQueries,
            geo_performance: geoPerformance,
            insights,
            recommendations
        };

        console.log('Data refresh complete');

        return {
            statusCode: 200,
            headers,
            body: JSON.stringify(data)
        };

    } catch (error) {
        console.error('Error fetching Google Ads data:', error);

        return {
            statusCode: 500,
            headers,
            body: JSON.stringify({
                error: 'Failed to fetch Google Ads data',
                message: error.message
            })
        };
    }
};

// Generate insights based on data
function generateInsights(summary, campaigns, keywords, searchQueries) {
    const insights = [];

    // Low quality keywords
    const lowQualityKeywords = keywords.filter(k => k.quality_score && k.quality_score < 5);
    if (lowQualityKeywords.length > 0) {
        insights.push({
            type: 'warning',
            title: 'Low Quality Scores',
            description: `${lowQualityKeywords.length} keywords have quality scores below 5. Improving ad relevance and landing pages could reduce CPC by 20-30%.`
        });
    }

    // Wasted spend on search queries
    const wastedQueries = searchQueries.filter(sq => sq.conversions === 0 && sq.cost > 10);
    const totalWasted = wastedQueries.reduce((sum, sq) => sum + sq.cost, 0);
    if (wastedQueries.length > 0) {
        insights.push({
            type: 'alert',
            title: 'Wasted Ad Spend',
            description: `RM ${totalWasted.toFixed(2)} spent on ${wastedQueries.length} search queries with zero conversions. Consider adding negative keywords.`
        });
    }

    // High-performing keywords
    const topKeyword = keywords.find(k => k.quality_score >= 8 && k.ctr >= 3);
    if (topKeyword) {
        insights.push({
            type: 'opportunity',
            title: 'High-Performing Keyword',
            description: `'${topKeyword.keyword}' has a ${topKeyword.ctr.toFixed(1)}% CTR and quality score of ${topKeyword.quality_score}. Consider increasing bids to capture more impression share.`
        });
    }

    // Quality score insight
    if (summary.avg_quality_score > 0) {
        const qsType = summary.avg_quality_score >= 7 ? 'opportunity' : 'warning';
        insights.push({
            type: qsType,
            title: 'Quality Score Overview',
            description: `Average quality score is ${summary.avg_quality_score.toFixed(1)}/10. ${summary.avg_quality_score >= 7 ? 'Great job maintaining high relevance!' : 'Consider improving ad relevance and landing page experience.'}`
        });
    }

    // Campaign status
    const pausedCampaigns = campaigns.filter(c => c.status === 'PAUSED');
    if (pausedCampaigns.length > 0) {
        insights.push({
            type: 'info',
            title: 'Campaign Status',
            description: `${pausedCampaigns.length} campaign(s) are currently PAUSED. Total historical spend: RM ${summary.total_spend.toFixed(2)}.`
        });
    }

    // CPA alert
    if (summary.total_conversions > 0 && summary.cost_per_conversion > 100) {
        insights.push({
            type: 'alert',
            title: 'High CPA Alert',
            description: `Cost per conversion is RM ${summary.cost_per_conversion.toFixed(2)}. Review conversion tracking and keyword targeting.`
        });
    } else if (summary.total_conversions === 0 && summary.total_spend > 0) {
        insights.push({
            type: 'alert',
            title: 'No Conversions',
            description: 'No conversions recorded. Verify conversion tracking is set up correctly in Google Ads.'
        });
    }

    return insights.slice(0, 6);
}

// Generate recommendations based on data
function generateRecommendations(summary, campaigns, keywords, searchQueries, campaignIdMap) {
    const recommendations = [];

    // Add negative keywords for wasted spend
    const wastedQueries = searchQueries.filter(sq => sq.conversions === 0 && sq.cost > 10);
    for (const sq of wastedQueries.slice(0, 3)) {
        recommendations.push({
            title: `Add Negative Keyword: ${sq.query}`,
            description: `RM ${sq.cost.toFixed(2)} spent with 0 conversions. Add as negative keyword to prevent wasted spend.`,
            impact: 'High',
            action_type: 'add_negative_keyword',
            keyword: sq.query,
            campaign_id: campaignIdMap[sq.campaign] || null,
            match_type: 'PHRASE'
        });
    }

    // Budget increase for top campaign
    const enabledCampaigns = campaigns.filter(c => c.status === 'ENABLED' && c.conversions > 0);
    const bestCampaign = enabledCampaigns.sort((a, b) => a.cpa - b.cpa)[0];
    if (bestCampaign) {
        recommendations.push({
            title: `Increase budget for ${bestCampaign.name}`,
            description: `This campaign has the lowest CPA (RM ${bestCampaign.cpa.toFixed(2)}). Increasing budget could generate more conversions efficiently.`,
            impact: 'High',
            action_type: 'bid_adjustment',
            campaign_id: bestCampaign.id
        });
    }

    // Pause low quality keywords
    const lowQualityKeywords = keywords.filter(k => k.quality_score && k.quality_score < 4 && k.clicks > 10);
    for (const kw of lowQualityKeywords.slice(0, 2)) {
        recommendations.push({
            title: `Pause Keyword: ${kw.keyword}`,
            description: `Quality score of ${kw.quality_score}/10 with ${kw.clicks} clicks. Low quality increases CPC.`,
            impact: 'Medium',
            action_type: 'keyword_action',
            keyword: kw.keyword,
            suggested_action: 'PAUSED'
        });
    }

    // Paused campaigns with good metrics
    const pausedCampaigns = campaigns.filter(c => c.status === 'PAUSED' && c.ctr > 2);
    if (pausedCampaigns.length > 0) {
        recommendations.push({
            title: 'Reactivate paused campaigns',
            description: `${pausedCampaigns.length} paused campaign(s) had good engagement metrics. Consider reactivating with updated ad copy.`,
            impact: 'Medium',
            action_type: 'review'
        });
    }

    // High CTR but low conversions
    const highCtrLowConv = campaigns.filter(c => c.ctr > 3 && c.conversions < 5 && c.clicks > 100);
    if (highCtrLowConv.length > 0) {
        recommendations.push({
            title: 'Improve landing page conversion',
            description: `${highCtrLowConv.length} campaign(s) have high CTR but low conversions. Review landing page experience and call-to-action.`,
            impact: 'High',
            action_type: 'review'
        });
    }

    // General recommendation if few specific ones
    if (recommendations.length < 3) {
        recommendations.push({
            title: 'Review search terms report',
            description: 'Regularly review search terms and add irrelevant queries as negative keywords to improve targeting efficiency.',
            impact: 'Medium',
            action_type: 'review'
        });
    }

    return recommendations.slice(0, 8);
}
