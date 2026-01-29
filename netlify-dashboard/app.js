/**
 * Google Ads Insights Dashboard - Client-Side JavaScript
 * Fetches data from data.json and renders the dashboard
 */

// Configuration
const CONFIG = {
    dataUrl: 'data.json',
    refreshEndpoint: '/.netlify/functions/refresh-data',
    currency: 'MYR',
    dateFormat: { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }
};

// DOM Elements
const elements = {
    loadingState: document.getElementById('loadingState'),
    errorState: document.getElementById('errorState'),
    errorMessage: document.getElementById('errorMessage'),
    dashboardContent: document.getElementById('dashboardContent'),
    lastUpdated: document.getElementById('lastUpdated'),
    accountName: document.getElementById('accountName'),
    dateRange: document.getElementById('dateRange'),
    refreshBtn: document.getElementById('refreshBtn'),

    // KPI elements
    totalSpend: document.getElementById('totalSpend'),
    spendTrend: document.getElementById('spendTrend'),
    totalConversions: document.getElementById('totalConversions'),
    conversionsTrend: document.getElementById('conversionsTrend'),
    costPerConversion: document.getElementById('costPerConversion'),
    cpaTrend: document.getElementById('cpaTrend'),
    avgQualityScore: document.getElementById('avgQualityScore'),
    qsTrend: document.getElementById('qsTrend'),

    // Table elements
    campaignTableBody: document.getElementById('campaignTableBody'),
    keywordTableBody: document.getElementById('keywordTableBody'),
    searchQueryTableBody: document.getElementById('searchQueryTableBody'),
    geoTableBody: document.getElementById('geoTableBody'),
    insightsGrid: document.getElementById('insightsGrid'),
    recommendationsList: document.getElementById('recommendationsList')
};

// Utility Functions
function formatCurrency(amount, currency = CONFIG.currency) {
    return `${currency} ${Number(amount).toLocaleString('en-MY', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatNumber(num) {
    return Number(num).toLocaleString('en-MY');
}

function formatPercent(num) {
    return `${Number(num).toFixed(2)}%`;
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString('en-MY', CONFIG.dateFormat);
}

function getStatusClass(status) {
    const statusMap = {
        'ENABLED': 'active',
        'PAUSED': 'paused',
        'REMOVED': 'removed'
    };
    return statusMap[status] || 'active';
}

function getQualityScoreClass(score) {
    if (score >= 7) return 'high';
    if (score >= 5) return 'medium';
    return 'low';
}

function getTrendHtml(value, inverted = false) {
    if (!value || value === 0) return '';
    const isPositive = inverted ? value < 0 : value > 0;
    const className = isPositive ? 'positive' : 'negative';
    const arrow = value > 0 ? '↑' : '↓';
    return `<span class="kpi-trend ${className}">${arrow} ${Math.abs(value).toFixed(1)}%</span>`;
}

// Show/Hide States
function showLoading() {
    elements.loadingState.style.display = 'flex';
    elements.errorState.style.display = 'none';
    elements.dashboardContent.style.display = 'none';
}

function showError(message) {
    elements.loadingState.style.display = 'none';
    elements.errorState.style.display = 'flex';
    elements.dashboardContent.style.display = 'none';
    elements.errorMessage.textContent = message;
}

function showDashboard() {
    elements.loadingState.style.display = 'none';
    elements.errorState.style.display = 'none';
    elements.dashboardContent.style.display = 'block';
}

// Render Functions
function renderKPIs(data) {
    const summary = data.summary || {};
    const trends = data.trends || {};

    elements.totalSpend.textContent = formatCurrency(summary.total_spend || 0);
    elements.spendTrend.innerHTML = getTrendHtml(trends.spend_change);

    elements.totalConversions.textContent = formatNumber(summary.total_conversions || 0);
    elements.conversionsTrend.innerHTML = getTrendHtml(trends.conversions_change);

    elements.costPerConversion.textContent = formatCurrency(summary.cost_per_conversion || 0);
    elements.cpaTrend.innerHTML = getTrendHtml(trends.cpa_change, true); // Lower is better

    elements.avgQualityScore.textContent = summary.avg_quality_score ? summary.avg_quality_score.toFixed(1) : '--';
    elements.qsTrend.innerHTML = getTrendHtml(trends.quality_score_change);
}

function renderCampaignTable(campaigns) {
    if (!campaigns || campaigns.length === 0) {
        elements.campaignTableBody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No campaign data available</td></tr>';
        return;
    }

    elements.campaignTableBody.innerHTML = campaigns.map(campaign => `
        <tr>
            <td><strong>${escapeHtml(campaign.name || campaign.campaign_name || 'Unknown')}</strong></td>
            <td><span class="status-badge ${getStatusClass(campaign.status)}">${campaign.status || 'ENABLED'}</span></td>
            <td>${formatCurrency(campaign.spend || campaign.cost || 0)}</td>
            <td>${formatNumber(campaign.impressions || 0)}</td>
            <td>${formatNumber(campaign.clicks || 0)}</td>
            <td>${formatPercent(campaign.ctr || 0)}</td>
            <td>${formatNumber(campaign.conversions || 0)}</td>
            <td>${formatCurrency(campaign.cpa || campaign.cost_per_conversion || 0)}</td>
        </tr>
    `).join('');
}

function renderKeywordTable(keywords) {
    if (!keywords || keywords.length === 0) {
        elements.keywordTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No keyword data available</td></tr>';
        return;
    }

    // Show top 10 keywords by impressions
    const topKeywords = keywords.slice(0, 10);

    elements.keywordTableBody.innerHTML = topKeywords.map(keyword => `
        <tr>
            <td><strong>${escapeHtml(keyword.keyword || keyword.keyword_text || 'Unknown')}</strong></td>
            <td>${escapeHtml(keyword.campaign || keyword.campaign_name || '-')}</td>
            <td>${formatNumber(keyword.impressions || 0)}</td>
            <td>${formatNumber(keyword.clicks || 0)}</td>
            <td>${formatPercent(keyword.ctr || 0)}</td>
            <td>${formatCurrency(keyword.avg_cpc || keyword.cpc || 0)}</td>
            <td><span class="quality-score ${getQualityScoreClass(keyword.quality_score || 0)}">${keyword.quality_score || '-'}</span></td>
        </tr>
    `).join('');
}

function renderSearchQueries(searchQueries) {
    if (!elements.searchQueryTableBody) return;

    if (!searchQueries || searchQueries.length === 0) {
        elements.searchQueryTableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No search query data available</td></tr>';
        return;
    }

    elements.searchQueryTableBody.innerHTML = searchQueries.map(sq => `
        <tr>
            <td><strong>${escapeHtml(sq.query || 'Unknown')}</strong></td>
            <td>${escapeHtml(sq.campaign || '-')}</td>
            <td>${formatNumber(sq.impressions || 0)}</td>
            <td>${formatNumber(sq.clicks || 0)}</td>
            <td>${formatCurrency(sq.cost || 0)}</td>
            <td>${formatNumber(sq.conversions || 0)}</td>
        </tr>
    `).join('');
}

// Location ID to name mapping (Google Ads Geo Criterion IDs)
const locationNames = {
    2458: 'Malaysia',
    2702: 'Singapore',
    2764: 'Thailand',
    2360: 'Vietnam',
    2356: 'India',
    2050: 'Australia',
    2586: 'Pakistan',
    2566: 'New Zealand',
    2288: 'Japan',
    2231: 'Hong Kong',
    2156: 'China',
    2840: 'United States',
    2826: 'United Kingdom',
    2276: 'Germany',
    2250: 'France',
    2380: 'Italy',
    2036: 'Spain',
    2124: 'Canada',
    2076: 'Brazil',
    2484: 'Mexico',
    2410: 'South Korea',
    2158: 'Taiwan',
    2608: 'Philippines',
    2360: 'Indonesia'
};

function renderGeoPerformance(geoData) {
    if (!elements.geoTableBody) return;

    if (!geoData || geoData.length === 0) {
        elements.geoTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No geographic data available</td></tr>';
        return;
    }

    // Group by location and sort by clicks
    const topGeo = geoData.slice(0, 10);

    elements.geoTableBody.innerHTML = topGeo.map(geo => {
        const locationName = geo.location_name || locationNames[geo.country_criterion_id] || `Region ${geo.country_criterion_id || 'Unknown'}`;
        const locationType = geo.location_type === 'AREA_OF_INTEREST' ? '(Interest)' : '(Presence)';
        return `
        <tr>
            <td><strong>${escapeHtml(locationName)}</strong> <small style="color: var(--text-muted)">${locationType}</small></td>
            <td>${escapeHtml(geo.campaign_name || geo.campaign || '-')}</td>
            <td>${formatNumber(geo.impressions || 0)}</td>
            <td>${formatNumber(geo.clicks || 0)}</td>
            <td>${formatPercent((geo.ctr || 0) * 100)}</td>
            <td>${formatCurrency(geo.cost || 0)}</td>
            <td>${formatNumber(geo.conversions || 0)}</td>
        </tr>
    `}).join('');
}

function renderInsights(insights) {
    if (!insights || insights.length === 0) {
        elements.insightsGrid.innerHTML = '<div class="insight-card"><p style="color: var(--text-muted);">No insights available</p></div>';
        return;
    }

    const typeMap = {
        'positive': 'opportunity',
        'opportunity': 'opportunity',
        'warning': 'warning',
        'negative': 'alert',
        'alert': 'alert',
        'info': 'info',
        'neutral': 'info'
    };

    elements.insightsGrid.innerHTML = insights.slice(0, 6).map(insight => {
        const type = typeMap[insight.type?.toLowerCase()] || 'info';
        return `
            <div class="insight-card">
                <span class="insight-type ${type}">${type}</span>
                <h3>${escapeHtml(insight.title || 'Insight')}</h3>
                <p>${escapeHtml(insight.description || insight.message || '')}</p>
            </div>
        `;
    }).join('');
}

function renderRecommendations(recommendations) {
    if (!recommendations || recommendations.length === 0) {
        elements.recommendationsList.innerHTML = '<div class="recommendation-item"><p style="color: var(--text-muted);">No recommendations available</p></div>';
        return;
    }

    const impactMap = {
        'high': 'high',
        'medium': 'medium',
        'low': 'low'
    };

    elements.recommendationsList.innerHTML = recommendations.slice(0, 8).map((rec, index) => {
        const impact = impactMap[rec.impact?.toLowerCase()] || 'medium';

        // Determine if action can be applied automatically
        let canApply = false;
        let buttonLabel = 'Apply';

        if (rec.action_type === 'keyword_action' && rec.keyword && rec.target_id?.includes('adGroupCriteria')) {
            // Pause/Enable keywords
            canApply = rec.suggested_action === 'PAUSED' || rec.suggested_action === 'ENABLED';
            buttonLabel = rec.suggested_action === 'PAUSED' ? 'Pause' : 'Enable';
        } else if (rec.action_type === 'add_negative_keyword' && rec.keyword && rec.campaign_id) {
            // Add negative keywords (requires campaign_id)
            canApply = true;
            buttonLabel = 'Add Negative';
        } else if (rec.action_type === 'bid_adjustment' && rec.target_id) {
            // Bid adjustments - can apply with user input for new bid
            canApply = true;
            buttonLabel = 'Adjust Bid';
        }

        return `
            <div class="recommendation-item">
                <div class="recommendation-content">
                    <h4>${escapeHtml(rec.title || rec.recommendation || 'Recommendation')}</h4>
                    <p>${escapeHtml(rec.description || rec.details || '')}</p>
                </div>
                <div class="recommendation-actions">
                    <span class="impact-badge ${impact}">${rec.impact || 'Medium'} Impact</span>
                    ${canApply ? `<button class="action-btn" onclick="applyRecommendation(${index})">${buttonLabel}</button>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Data Loading
async function loadData() {
    showLoading();

    try {
        const response = await fetch(CONFIG.dataUrl);

        if (!response.ok) {
            throw new Error(`Failed to load data: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();

        // Update metadata
        elements.lastUpdated.textContent = formatDate(data.generated_at || data.last_updated);
        elements.accountName.textContent = data.account_name || `Customer ID: ${data.customer_id || 'Unknown'}`;

        if (data.date_range) {
            const start = data.date_range.start_date || data.date_range.start || 'N/A';
            const end = data.date_range.end_date || data.date_range.end || 'N/A';
            elements.dateRange.textContent = `${start} to ${end}`;
        }

        // Store data globally for recommendations
        window.dashboardData = data;

        // Render all sections
        renderKPIs(data);
        renderCampaignTable(data.campaigns || []);
        renderKeywordTable(data.keywords || []);
        renderSearchQueries(data.search_queries || []);
        renderGeoPerformance(data.geo_performance || []);
        renderInsights(data.insights || []);
        renderRecommendations(data.recommendations || []);

        showDashboard();

    } catch (error) {
        console.error('Error loading data:', error);
        showError(error.message || 'Failed to load dashboard data');
    }
}

// Refresh Data Function
async function refreshData() {
    const btn = elements.refreshBtn;
    btn.disabled = true;
    btn.classList.add('loading');

    try {
        const response = await fetch(CONFIG.refreshEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `Refresh failed: ${response.status}`);
        }

        // Reload data after refresh
        await loadData();

    } catch (error) {
        console.error('Error refreshing data:', error);
        alert(`Failed to refresh data: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.classList.remove('loading');
    }
}

// Smooth scroll for navigation
document.querySelectorAll('.nav-item[href^="#"]').forEach(link => {
    link.addEventListener('click', function(e) {
        const href = this.getAttribute('href');
        if (href === '#') return;

        e.preventDefault();
        const target = document.querySelector(href);
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        // Update active state
        document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
        this.classList.add('active');
    });
});

// Change Date Range Function
async function changeDateRange(days) {
    if (days === 'custom') {
        alert('Custom date range requires the refresh-data function to be updated.\n\nFor now, please use the predefined ranges.');
        document.getElementById('dateRangeSelect').value = '30';
        return;
    }

    const daysNum = parseInt(days, 10);
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - daysNum);

    const formatDateStr = (d) => d.toISOString().split('T')[0];

    // Show loading state
    const btn = elements.refreshBtn;
    btn.disabled = true;
    btn.classList.add('loading');

    try {
        const response = await fetch(CONFIG.refreshEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                start_date: formatDateStr(startDate),
                end_date: formatDateStr(endDate),
                days: daysNum
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `Refresh failed: ${response.status}`);
        }

        // Reload data after refresh
        await loadData();
        alert(`Data refreshed for last ${daysNum} days`);

    } catch (error) {
        console.error('Error changing date range:', error);
        alert(`Failed to refresh data: ${error.message}\n\nNote: The refresh function needs Google Ads API credentials configured in Netlify.`);
    } finally {
        btn.disabled = false;
        btn.classList.remove('loading');
    }
}

// Apply Recommendation Function
async function applyRecommendation(index) {
    const rec = window.dashboardData?.recommendations?.[index];
    if (!rec) {
        alert('Recommendation not found');
        return;
    }

    // Build confirmation message based on action type
    let confirmMessage = '';
    if (rec.action_type === 'keyword_action') {
        const action = rec.suggested_action === 'PAUSED' ? 'pause' : 'enable';
        confirmMessage = `Are you sure you want to ${action} the keyword "${rec.keyword}"?\n\nThis will immediately ${action} this keyword in Google Ads.`;
    } else if (rec.action_type === 'add_negative_keyword') {
        confirmMessage = `Are you sure you want to add "${rec.keyword}" as a negative keyword?\n\nThis will prevent your ads from showing for searches containing this term.`;
    } else if (rec.action_type === 'bid_adjustment') {
        // For bid adjustments, prompt for new bid amount
        const currentBid = rec.current_bid ? `Current bid: RM ${rec.current_bid.toFixed(2)}\n` : '';
        const suggestedBid = rec.suggested_bid ? `Suggested bid: RM ${rec.suggested_bid.toFixed(2)}\n\n` : '\n';

        const newBidInput = prompt(
            `${currentBid}${suggestedBid}Enter the new bid amount for "${rec.keyword}" (in MYR):`,
            rec.suggested_bid ? rec.suggested_bid.toFixed(2) : ''
        );

        if (newBidInput === null) return; // User cancelled

        const newBid = parseFloat(newBidInput);
        if (isNaN(newBid) || newBid <= 0) {
            alert('Please enter a valid bid amount greater than 0');
            return;
        }

        if (!confirm(`Are you sure you want to change the bid for "${rec.keyword}" to RM ${newBid.toFixed(2)}?\n\nThis will immediately update the bid in Google Ads.`)) {
            return;
        }

        // Apply bid adjustment with the new bid
        try {
            const response = await fetch('/.netlify/functions/apply-recommendation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action_type: rec.action_type,
                    target_id: rec.target_id,
                    keyword: rec.keyword,
                    new_bid: newBid
                })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || result.message || 'Failed to adjust bid');
            }

            alert(result.message || `Bid adjusted to RM ${newBid.toFixed(2)} successfully!`);
            await loadData();
        } catch (error) {
            console.error('Error adjusting bid:', error);
            alert(`Failed to adjust bid: ${error.message}\n\nMake sure Google Ads API credentials are configured in Netlify.`);
        }
        return;
    } else {
        confirmMessage = `Are you sure you want to apply this recommendation?\n\nAction: ${rec.title}`;
    }

    if (!confirm(confirmMessage)) return;

    try {
        const response = await fetch('/.netlify/functions/apply-recommendation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action_type: rec.action_type,
                target_id: rec.target_id,
                keyword: rec.keyword,
                suggested_action: rec.suggested_action,
                campaign_id: rec.campaign_id,
                match_type: rec.match_type || 'PHRASE'
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || result.message || 'Failed to apply recommendation');
        }

        if (result.manual_action_required) {
            alert(result.message);
            if (result.google_ads_url) {
                window.open(result.google_ads_url, '_blank');
            }
        } else {
            alert(result.message || 'Recommendation applied successfully!');
            // Reload data to show updated status
            await loadData();
        }

    } catch (error) {
        console.error('Error applying recommendation:', error);
        alert(`Failed to apply recommendation: ${error.message}\n\nMake sure Google Ads API credentials are configured in Netlify.`);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', loadData);
