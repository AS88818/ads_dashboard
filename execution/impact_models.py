"""
Impact modeling formulas for advertising recommendations.
Provides concrete, quantified impact calculations with confidence levels.
"""


def calculate_exclusion_impact(spend, conversions=0):
    """
    Calculate impact of excluding zero-converting audiences/placements.

    Assumptions:
    - Zero conversions = all spend is waste
    - Trend continues if not excluded

    Args:
        spend: Weekly spend on the segment
        conversions: Number of conversions (should be 0 for exclusions)

    Returns:
        dict with monthly_savings, confidence, confidence_pct, formula
    """
    monthly_savings = spend * 4

    return {
        'monthly_savings': monthly_savings,
        'additional_conversions_monthly': 0,
        'additional_revenue_monthly': 0,
        'confidence': 'high',
        'confidence_pct': 90,
        'formula': f"Weekly spend (RM {spend:.2f}) × 4 weeks = RM {monthly_savings:.2f} saved",
        'assumptions': [
            'Segment has 0 conversions, all spend is waste',
            'Trend continues if not excluded'
        ]
    }


def calculate_scaling_impact(current_spend, current_conversions, scale_factor=1.25, customer_value=None):
    """
    Calculate impact of scaling budget for top performers.

    Assumptions:
    - 25% budget increase → 20% volume increase (diminishing returns)
    - CPA increases 10% (lower intent traffic as you scale)
    - Default customer value: Conservative estimate based on CPA

    Args:
        current_spend: Weekly spend
        current_conversions: Weekly conversions
        scale_factor: Budget multiplier (1.25 = 25% increase)
        customer_value: Revenue per conversion (if None, uses conservative 3× CPA estimate)

    Returns:
        dict with impact metrics, confidence, formula
    """
    if current_conversions == 0:
        return {
            'monthly_savings': 0,
            'additional_conversions_monthly': 0,
            'additional_revenue_monthly': 0,
            'confidence': 'low',
            'confidence_pct': 30,
            'formula': 'No conversions to scale from',
            'assumptions': []
        }

    # Calculate current CPA
    current_cpa = current_spend / current_conversions

    # If no customer value provided, use conservative estimate (3× CPA = 200% ROI target)
    if customer_value is None:
        customer_value = current_cpa * 3
        value_note = f'RM {customer_value:.0f} (estimated 3× CPA)'
    else:
        value_note = f'RM {customer_value}'

    # Diminishing returns: volume doesn't scale 1:1 with budget
    volume_increase_rate = 0.20  # 25% budget → 20% volume
    cpa_degradation = 1.10  # CPA gets 10% worse

    new_cpa = current_cpa * cpa_degradation
    additional_conversions = current_conversions * volume_increase_rate
    additional_revenue = additional_conversions * customer_value
    additional_spend = additional_conversions * new_cpa
    net_benefit = additional_revenue - additional_spend

    return {
        'monthly_savings': 0,
        'additional_conversions_monthly': additional_conversions * 4,
        'additional_spend_monthly': additional_spend * 4,
        'additional_revenue_monthly': additional_revenue * 4,
        'net_benefit_monthly': net_benefit * 4,
        'new_cpa': new_cpa,
        'confidence': 'moderate',
        'confidence_pct': 70,
        'formula': f"{current_conversions:.1f} conv × 20% growth × {value_note} - {additional_conversions:.1f} conv × RM {new_cpa:.2f} CPA",
        'assumptions': [
            f'{int((scale_factor - 1) * 100)}% budget increase → 20% volume increase (diminishing returns)',
            'CPA increases 10% (lower intent traffic)',
            f'Customer value: {value_note}'
        ]
    }


def calculate_creative_refresh_impact(spend, frequency, current_ctr, current_conversions, customer_value=None):
    """
    Calculate impact of refreshing fatigued creatives.

    Assumptions based on frequency severity:
    - Frequency > 5: CTR +40%, Conv Rate +10%
    - Frequency 3-5: CTR +25%, Conv Rate +10%

    Args:
        spend: Weekly ad spend
        frequency: Current ad frequency
        current_ctr: Current click-through rate (decimal)
        current_conversions: Weekly conversions
        customer_value: Revenue per conversion

    Returns:
        dict with impact metrics, confidence, formula
    """
    # Impact varies by frequency severity
    if frequency > 5:
        ctr_improvement = 0.40
        conv_rate_improvement = 0.10
        confidence_pct = 75
    elif frequency > 3:
        ctr_improvement = 0.25
        conv_rate_improvement = 0.10
        confidence_pct = 70
    else:
        ctr_improvement = 0.15
        conv_rate_improvement = 0.05
        confidence_pct = 60

    # Calculate customer value if not provided
    if current_conversions > 0 and customer_value is None:
        current_cpa = spend / current_conversions
        customer_value = current_cpa * 3
        value_note = f'RM {customer_value:.0f} (estimated 3× CPA)'
    elif customer_value is None:
        customer_value = 100  # Fallback default
        value_note = 'RM 100 (estimated)'
    else:
        value_note = f'RM {customer_value}'

    # Additional conversions from improved conversion rate
    additional_conversions = current_conversions * conv_rate_improvement
    additional_revenue = additional_conversions * customer_value

    # Cost stays same (using existing budget more efficiently)
    net_benefit = additional_revenue

    return {
        'monthly_savings': 0,
        'additional_conversions_monthly': additional_conversions * 4,
        'additional_revenue_monthly': additional_revenue * 4,
        'net_benefit_monthly': net_benefit * 4,
        'ctr_improvement_pct': int(ctr_improvement * 100),
        'conv_rate_improvement_pct': int(conv_rate_improvement * 100),
        'confidence': 'moderate',
        'confidence_pct': confidence_pct,
        'formula': f"CTR +{int(ctr_improvement * 100)}% + Conv Rate +{int(conv_rate_improvement * 100)}% = {additional_conversions:.1f} more conv/week",
        'assumptions': [
            f'Frequency {frequency:.1f} indicates creative fatigue',
            f'CTR improvement: +{int(ctr_improvement * 100)}%',
            f'Conversion rate improvement: +{int(conv_rate_improvement * 100)}%',
            f'Customer value: {value_note}'
        ]
    }


def calculate_schedule_impact(wasted_hours_spend, avg_conv_rate=0.02, peak_multiplier=2.5, avg_cpa=50, customer_value=None):
    """
    Calculate impact of adjusting ad schedule to avoid wasted hours.

    Assumptions:
    - Peak hours convert at 2.5x average rate
    - Redirect wasted hour spend to peak hours
    - Average CPA: RM 50

    Args:
        wasted_hours_spend: Weekly spend in low-performing hours
        avg_conv_rate: Average conversion rate
        peak_multiplier: How much better peak hours perform
        avg_cpa: Average cost per acquisition
        customer_value: Revenue per conversion

    Returns:
        dict with impact metrics, confidence, formula
    """
    # Calculate customer value if not provided (conservative 3× CPA)
    if customer_value is None:
        customer_value = avg_cpa * 3
        value_note = f'RM {customer_value:.0f} (estimated 3× CPA)'
    else:
        value_note = f'RM {customer_value}'

    # Conversions if we redirect to peak hours
    redirected_conversions = (wasted_hours_spend / avg_cpa) * peak_multiplier
    additional_revenue = redirected_conversions * customer_value

    # Savings from not wasting money in bad hours (don't double-count with revenue)
    monthly_savings = 0  # Conservative: don't count savings AND revenue

    return {
        'monthly_savings': monthly_savings,
        'additional_conversions_monthly': redirected_conversions * 4,
        'additional_revenue_monthly': additional_revenue * 4,
        'net_benefit_monthly': additional_revenue * 4,
        'confidence': 'moderate',
        'confidence_pct': 70,
        'formula': f"RM {wasted_hours_spend:.2f} redirected to peak hours ({peak_multiplier}× conversion rate)",
        'assumptions': [
            'Peak hours convert at 2.5× average rate',
            f'Redirect RM {wasted_hours_spend:.2f}/week to peak hours',
            f'Average CPA: RM {avg_cpa}',
            f'Customer value: {value_note}'
        ]
    }


def calculate_bid_adjustment_impact(current_bid, suggested_bid, keyword_spend, keyword_conversions, customer_value=None):
    """
    Calculate impact of bid adjustments (Google Ads).

    Assumptions:
    - For increases: +25% bid → +20% impressions (80% efficiency)
    - For decreases: -35% bid → save 35% spend, lose 20% conversions

    Args:
        current_bid: Current max CPC bid
        suggested_bid: Recommended max CPC bid
        keyword_spend: Weekly keyword spend
        keyword_conversions: Weekly keyword conversions
        customer_value: Revenue per conversion

    Returns:
        dict with impact metrics, confidence, formula
    """
    if current_bid == 0:
        return {
            'monthly_savings': 0,
            'additional_conversions_monthly': 0,
            'additional_revenue_monthly': 0,
            'confidence': 'low',
            'confidence_pct': 30,
            'formula': 'Invalid current bid',
            'assumptions': []
        }

    bid_change_pct = (suggested_bid - current_bid) / current_bid

    # Calculate customer value if not provided
    if keyword_conversions > 0 and customer_value is None:
        current_cpa = keyword_spend / keyword_conversions
        customer_value = current_cpa * 3
        value_note = f'RM {customer_value:.0f} (estimated 3× CPA)'
    elif customer_value is None:
        customer_value = 100  # Fallback default
        value_note = 'RM 100 (estimated)'
    else:
        value_note = f'RM {customer_value}'

    if bid_change_pct > 0:  # Increase bid
        # Volume doesn't scale 1:1 with bid - use 80% efficiency
        volume_increase = bid_change_pct * 0.8
        additional_conversions = keyword_conversions * volume_increase if keyword_conversions > 0 else 0
        additional_revenue = additional_conversions * customer_value
        additional_spend = keyword_spend * bid_change_pct
        net_benefit = additional_revenue - additional_spend

        return {
            'monthly_savings': 0,
            'additional_conversions_monthly': additional_conversions * 4,
            'additional_spend_monthly': additional_spend * 4,
            'additional_revenue_monthly': additional_revenue * 4,
            'net_benefit_monthly': net_benefit * 4,
            'confidence': 'moderate',
            'confidence_pct': 70,
            'formula': f"+{int(bid_change_pct * 100)}% bid → +{int(volume_increase * 100)}% volume = {additional_conversions:.1f} conv/week",
            'assumptions': [
                f'{int(bid_change_pct * 100)}% bid increase → {int(volume_increase * 100)}% volume increase (80% efficiency)',
                f'Customer value: {value_note}'
            ]
        }
    else:  # Decrease bid
        savings = abs(keyword_spend * bid_change_pct)
        conversions_lost = keyword_conversions * 0.20 if keyword_conversions > 0 else 0  # Lose 20% of conversions

        return {
            'monthly_savings': savings * 4,
            'conversions_lost_monthly': conversions_lost * 4,
            'additional_conversions_monthly': -conversions_lost,
            'net_benefit_monthly': savings * 4,
            'confidence': 'moderate',
            'confidence_pct': 70,
            'formula': f"{int(abs(bid_change_pct) * 100)}% bid cut → save RM {savings:.2f}/week",
            'assumptions': [
                f'{int(abs(bid_change_pct) * 100)}% bid decrease → save {int(abs(bid_change_pct) * 100)}% spend',
                'Lose ~20% of conversions'
            ]
        }


def calculate_geo_adjustment_impact(current_spend, current_conversions, geo_performance_multiplier, customer_value=None):
    """
    Calculate impact of geographic bid adjustments or exclusions.

    Args:
        current_spend: Weekly spend in the geo
        current_conversions: Weekly conversions in the geo
        geo_performance_multiplier: How this geo performs vs average (e.g., 1.5 = 50% better)
        customer_value: Revenue per conversion

    Returns:
        dict with impact metrics, confidence, formula
    """
    if geo_performance_multiplier < 0.5:
        # Poor performing geo - recommend exclusion
        return calculate_exclusion_impact(current_spend, current_conversions)
    elif geo_performance_multiplier > 1.5:
        # High performing geo - recommend scaling
        return calculate_scaling_impact(current_spend, current_conversions, scale_factor=1.20, customer_value=customer_value)
    else:
        # Calculate customer value if not provided
        if current_conversions > 0 and customer_value is None:
            current_cpa = current_spend / current_conversions
            customer_value = current_cpa * 3
            value_note = f'RM {customer_value:.0f} (estimated 3× CPA)'
        elif customer_value is None:
            customer_value = 100  # Fallback default
            value_note = 'RM 100 (estimated)'
        else:
            value_note = f'RM {customer_value}'

        # Moderate adjustment
        bid_adjustment = (geo_performance_multiplier - 1.0) * 0.5  # Conservative adjustment
        spend_change = current_spend * bid_adjustment
        conversions_change = current_conversions * bid_adjustment * 0.8  # 80% efficiency
        revenue_change = conversions_change * customer_value
        net_benefit = revenue_change - spend_change

        return {
            'monthly_savings': -spend_change * 4 if spend_change < 0 else 0,
            'additional_conversions_monthly': conversions_change * 4,
            'additional_spend_monthly': spend_change * 4 if spend_change > 0 else 0,
            'additional_revenue_monthly': revenue_change * 4,
            'net_benefit_monthly': net_benefit * 4,
            'confidence': 'moderate',
            'confidence_pct': 70,
            'formula': f"Geo performs {geo_performance_multiplier:.1f}x avg → {int(bid_adjustment * 100)}% bid adjustment",
            'assumptions': [
                f'Geographic performance: {geo_performance_multiplier:.1f}× average',
                'Conservative bid adjustment (50% of performance difference)',
                f'Customer value: {value_note}'
            ]
        }


def calculate_budget_adjustment_impact(current_budget, suggested_budget, current_conversions, customer_value=None):
    """
    Calculate impact of campaign budget adjustments.

    Args:
        current_budget: Current daily budget
        suggested_budget: Recommended daily budget
        current_conversions: Daily conversions
        customer_value: Revenue per conversion

    Returns:
        dict with impact metrics, confidence, formula
    """
    budget_change_pct = (suggested_budget - current_budget) / current_budget if current_budget > 0 else 0

    if budget_change_pct > 0:
        # Increase budget - use scaling model
        weekly_spend = current_budget * 7
        weekly_conversions = current_conversions * 7
        scale_factor = 1 + budget_change_pct
        return calculate_scaling_impact(weekly_spend, weekly_conversions, scale_factor, customer_value)
    else:
        # Decrease budget (usually for underperformers)
        savings = abs(current_budget - suggested_budget) * 30  # Monthly
        conversions_lost = current_conversions * abs(budget_change_pct) * 30

        return {
            'monthly_savings': savings,
            'conversions_lost_monthly': conversions_lost,
            'additional_conversions_monthly': -conversions_lost,
            'net_benefit_monthly': savings,
            'confidence': 'moderate',
            'confidence_pct': 70,
            'formula': f"{int(abs(budget_change_pct) * 100)}% budget cut → save RM {savings:.2f}/month",
            'assumptions': [
                f'{int(abs(budget_change_pct) * 100)}% budget decrease',
                'Proportional conversion loss expected'
            ]
        }


def get_automation_metadata(rec_type, platform='facebook'):
    """
    Get automation metadata for a recommendation type.

    Args:
        rec_type: Recommendation type
        platform: 'facebook' or 'google'

    Returns:
        dict with is_automatable, manual_reason
    """
    facebook_auto = {
        'audience_exclusion', 'creative_refresh', 'placement_exclusion',
        'budget_adjustment', 'geo_exclusion', 'schedule_adjustment',
        'budget_scaling', 'campaign_review', 'roas_scaling', 'roas_review',
        'geo_scaling', 'day_schedule'
    }

    facebook_manual_reasons = {
        'audience_fatigue': 'Creating lookalike audiences requires strategic decisions',
        'objective_mismatch': "Facebook API doesn't allow changing campaign objectives post-creation",
        'creative_test': 'A/B testing requires human creativity for new ad variations',
        'landing_page': 'Landing page optimization requires website CMS access'
    }

    google_auto = {
        'keyword_action', 'bid_adjustment', 'schedule_bid_adjustment',
        'geo_bid_adjustment', 'geo_exclusion', 'ad_copy'
    }

    google_manual_reasons = {
        'quality_improvement': 'Requires strategic improvements (landing page speed, ad relevance, promotional testing)',
        'budget_pacing': 'Informational only - no action required'
    }

    if platform == 'facebook':
        is_automatable = rec_type in facebook_auto
        manual_reason = facebook_manual_reasons.get(rec_type) if not is_automatable else None
    else:  # google
        is_automatable = rec_type in google_auto
        manual_reason = google_manual_reasons.get(rec_type) if not is_automatable else None

    return {
        'is_automatable': is_automatable,
        'manual_reason': manual_reason
    }
