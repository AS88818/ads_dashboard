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

    elements.insightsGrid.innerHTML = insights.slice(0, 4).map(insight => {
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

    elements.recommendationsList.innerHTML = recommendations.slice(0, 5).map(rec => {
        const impact = impactMap[rec.impact?.toLowerCase()] || 'medium';
        return `
            <div class="recommendation-item">
                <div class="recommendation-content">
                    <h4>${escapeHtml(rec.title || rec.recommendation || 'Recommendation')}</h4>
                    <p>${escapeHtml(rec.description || rec.details || '')}</p>
                </div>
                <div class="recommendation-impact">
                    <span class="impact-badge ${impact}">${rec.impact || 'Medium'} Impact</span>
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
            elements.dateRange.textContent = `${data.date_range.start} to ${data.date_range.end}`;
        }

        // Render all sections
        renderKPIs(data);
        renderCampaignTable(data.campaigns || []);
        renderKeywordTable(data.keywords || []);
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

// Initialize
document.addEventListener('DOMContentLoaded', loadData);
