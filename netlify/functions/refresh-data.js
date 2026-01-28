/**
 * Netlify Function: Refresh Google Ads Data
 *
 * This serverless function fetches data from Google Ads API
 * and generates insights for the dashboard.
 *
 * Environment variables required:
 * - GOOGLE_ADS_DEVELOPER_TOKEN
 * - GOOGLE_ADS_CLIENT_ID
 * - GOOGLE_ADS_CLIENT_SECRET
 * - GOOGLE_ADS_REFRESH_TOKEN
 * - GOOGLE_ADS_LOGIN_CUSTOMER_ID
 * - GOOGLE_ADS_CUSTOMER_ID (e.g., 7867388610 for YCK)
 */

const { GoogleAdsApi } = require('google-ads-api');

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

function calculateTrends(current, previous) {
    if (!previous || previous === 0) return 0;
    return ((current - previous) / previous) * 100;
}

// Main handler
exports.handler = async (event, context) => {
    // Only allow POST requests
    if (event.httpMethod !== 'POST') {
        return {
            statusCode: 405,
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
            body: JSON.stringify({
                error: 'Missing required environment variables',
                missing: missingVars
            })
        };
    }

    try {
        // Initialize Google Ads client
        const client = new GoogleAdsApi({
            client_id: process.env.GOOGLE_ADS_CLIENT_ID,
            client_secret: process.env.GOOGLE_ADS_CLIENT_SECRET,
            developer_token: process.env.GOOGLE_ADS_DEVELOPER_TOKEN
        });

        const customer = client.Customer({
            customer_id: process.env.GOOGLE_ADS_CUSTOMER_ID,
            login_customer_id: process.env.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
            refresh_token: process.env.GOOGLE_ADS_REFRESH_TOKEN
        });

        const dateRange = getDateRange(30);

        // Fetch campaign data
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

        const campaignResults = await customer.query(campaignQuery);

        // Fetch keyword data
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

        const keywordResults = await customer.query(keywordQuery);

        // Process campaign data
        const campaigns = campaignResults.map(row => ({
            name: row.campaign.name,
            status: row.campaign.status,
            spend: (row.metrics.cost_micros || 0) / 1000000,
            impressions: row.metrics.impressions || 0,
            clicks: row.metrics.clicks || 0,
            ctr: (row.metrics.ctr || 0) * 100,
            conversions: row.metrics.conversions || 0,
            cpa: row.metrics.conversions > 0
                ? (row.metrics.cost_micros / 1000000) / row.metrics.conversions
                : 0
        }));

        // Process keyword data
        const keywords = keywordResults.map(row => ({
            keyword: row.ad_group_criterion?.keyword?.text || 'Unknown',
            campaign: row.campaign?.name || '-',
            impressions: row.metrics.impressions || 0,
            clicks: row.metrics.clicks || 0,
            ctr: (row.metrics.ctr || 0) * 100,
            avg_cpc: (row.metrics.average_cpc || 0) / 1000000,
            quality_score: row.ad_group_criterion?.quality_info?.quality_score || null
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
        const insights = generateInsights(summary, campaigns, keywords);
        const recommendations = generateRecommendations(summary, campaigns, keywords);

        // Build final response
        const data = {
            customer_id: process.env.GOOGLE_ADS_CUSTOMER_ID,
            account_name: 'YCK Chiropractic',
            generated_at: new Date().toISOString(),
            date_range: dateRange,
            summary,
            trends: {
                spend_change: 0, // Would need historical data to calculate
                conversions_change: 0,
                cpa_change: 0,
                quality_score_change: 0
            },
            campaigns,
            keywords,
            insights,
            recommendations
        };

        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        };

    } catch (error) {
        console.error('Error fetching Google Ads data:', error);

        return {
            statusCode: 500,
            body: JSON.stringify({
                error: 'Failed to fetch Google Ads data',
                message: error.message
            })
        };
    }
};

// Generate insights based on data
function generateInsights(summary, campaigns, keywords) {
    const insights = [];

    // High-performing keywords
    const topKeyword = keywords.find(k => k.quality_score >= 8 && k.ctr >= 3);
    if (topKeyword) {
        insights.push({
            type: 'opportunity',
            title: 'High-Performing Keyword',
            description: `'${topKeyword.keyword}' has a ${topKeyword.ctr.toFixed(1)}% CTR and quality score of ${topKeyword.quality_score}. Consider increasing bids to capture more impression share.`
        });
    }

    // Budget pacing
    const topCampaign = campaigns[0];
    if (topCampaign && topCampaign.status === 'ENABLED') {
        insights.push({
            type: 'info',
            title: 'Top Campaign Performance',
            description: `'${topCampaign.name}' is your highest spending campaign with ${topCampaign.conversions} conversions at MYR ${topCampaign.cpa.toFixed(2)} CPA.`
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

    // Low quality keywords
    const lowQualityKeywords = keywords.filter(k => k.quality_score && k.quality_score < 5);
    if (lowQualityKeywords.length > 0) {
        insights.push({
            type: 'warning',
            title: 'Low Quality Score Keywords',
            description: `${lowQualityKeywords.length} keywords have quality scores below 5, which increases your cost per click. Review ad relevance and landing pages.`
        });
    }

    return insights.slice(0, 4);
}

// Generate recommendations based on data
function generateRecommendations(summary, campaigns, keywords) {
    const recommendations = [];

    // Budget increase for top campaign
    const enabledCampaigns = campaigns.filter(c => c.status === 'ENABLED' && c.conversions > 0);
    const bestCampaign = enabledCampaigns.sort((a, b) => a.cpa - b.cpa)[0];
    if (bestCampaign) {
        recommendations.push({
            title: `Increase budget for ${bestCampaign.name}`,
            description: `This campaign has the lowest CPA (MYR ${bestCampaign.cpa.toFixed(2)}). Increasing budget could generate more conversions efficiently.`,
            impact: 'High'
        });
    }

    // Pause low quality keywords
    const lowQualityKeywords = keywords.filter(k => k.quality_score && k.quality_score < 5);
    if (lowQualityKeywords.length > 0) {
        recommendations.push({
            title: 'Review low quality score keywords',
            description: `${lowQualityKeywords.length} keywords have quality scores below 5. Consider pausing or improving these to reduce costs.`,
            impact: 'Medium'
        });
    }

    // Paused campaigns with good metrics
    const pausedCampaigns = campaigns.filter(c => c.status === 'PAUSED' && c.ctr > 2);
    if (pausedCampaigns.length > 0) {
        recommendations.push({
            title: 'Reactivate paused campaigns',
            description: `${pausedCampaigns.length} paused campaign(s) had good engagement metrics. Consider reactivating with updated ad copy.`,
            impact: 'Medium'
        });
    }

    // High CTR but low conversions
    const highCtrLowConv = campaigns.filter(c => c.ctr > 3 && c.conversions < 5 && c.clicks > 100);
    if (highCtrLowConv.length > 0) {
        recommendations.push({
            title: 'Improve landing page conversion',
            description: `${highCtrLowConv.length} campaign(s) have high CTR but low conversions. Review landing page experience and call-to-action.`,
            impact: 'High'
        });
    }

    // General recommendation if few specific ones
    if (recommendations.length < 3) {
        recommendations.push({
            title: 'Add negative keywords',
            description: 'Review search terms report regularly and add irrelevant queries as negative keywords to improve targeting efficiency.',
            impact: 'Medium'
        });
    }

    return recommendations.slice(0, 5);
}
