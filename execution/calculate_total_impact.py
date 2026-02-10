"""
Calculate total expected benefits from all recommendations.
Aggregates individual recommendation impacts with confidence adjustments.
"""


def aggregate_total_benefits(recommendations, confidence_level='moderate'):
    """
    Calculate total expected benefits from implementing all recommendations.

    Args:
        recommendations: List of recommendation dicts with 'impact_data' field
        confidence_level: 'conservative' (50%), 'moderate' (70%), or 'optimistic' (100%)

    Returns:
        dict with total impacts, breakdown by type, and confidence info
    """
    confidence_factors = {
        'conservative': 0.5,
        'moderate': 0.7,
        'optimistic': 1.0
    }
    factor = confidence_factors.get(confidence_level, 0.7)

    totals = {
        'total_monthly_savings': 0.0,
        'total_additional_conversions': 0.0,
        'total_additional_revenue': 0.0,
        'total_additional_spend': 0.0,
        'total_net_benefit': 0.0,
        'total_recommendations': len(recommendations),
        'automatable_count': 0,
        'manual_count': 0,
        'confidence_level': confidence_level,
        'confidence_factor': factor,
        'breakdown_by_type': {},
        'breakdown_by_priority': {'high': 0, 'medium': 0, 'low': 0}
    }

    # Aggregate impacts
    for rec in recommendations:
        impact_data = rec.get('impact_data', {})
        rec_type = rec.get('type', 'unknown')
        priority = rec.get('priority', 'medium')
        automation = rec.get('automation', {})

        # Apply confidence factor to projections
        monthly_savings = impact_data.get('monthly_savings', 0) * factor
        additional_conversions = impact_data.get('additional_conversions_monthly', 0) * factor
        additional_revenue = impact_data.get('additional_revenue_monthly', 0) * factor
        additional_spend = impact_data.get('additional_spend_monthly', 0) * factor
        net_benefit = impact_data.get('net_benefit_monthly', 0) * factor

        # If net_benefit not provided, calculate it
        if net_benefit == 0 and (monthly_savings > 0 or additional_revenue > 0):
            net_benefit = monthly_savings + additional_revenue - additional_spend

        totals['total_monthly_savings'] += monthly_savings
        totals['total_additional_conversions'] += additional_conversions
        totals['total_additional_revenue'] += additional_revenue
        totals['total_additional_spend'] += additional_spend
        totals['total_net_benefit'] += net_benefit

        # Count automation
        if automation.get('is_automatable', False):
            totals['automatable_count'] += 1
        else:
            totals['manual_count'] += 1

        # Breakdown by type
        if rec_type not in totals['breakdown_by_type']:
            totals['breakdown_by_type'][rec_type] = {
                'count': 0,
                'monthly_savings': 0,
                'additional_conversions': 0,
                'additional_revenue': 0,
                'net_benefit': 0
            }

        totals['breakdown_by_type'][rec_type]['count'] += 1
        totals['breakdown_by_type'][rec_type]['monthly_savings'] += monthly_savings
        totals['breakdown_by_type'][rec_type]['additional_conversions'] += additional_conversions
        totals['breakdown_by_type'][rec_type]['additional_revenue'] += additional_revenue
        totals['breakdown_by_type'][rec_type]['net_benefit'] += net_benefit

        # Breakdown by priority
        if priority in totals['breakdown_by_priority']:
            totals['breakdown_by_priority'][priority] += 1

    return totals


def format_total_impact_summary(totals):
    """
    Format total impact data into human-readable summary text.

    Args:
        totals: Output from aggregate_total_benefits()

    Returns:
        Formatted string summary
    """
    summary = []

    summary.append(f"📊 Total Expected Impact ({totals['total_recommendations']} recommendations)")
    summary.append(f"Confidence Level: {totals['confidence_level'].title()} ({int(totals['confidence_factor'] * 100)}%)")
    summary.append("")

    summary.append("💰 Financial Impact:")
    summary.append(f"  • Monthly Savings: RM {totals['total_monthly_savings']:,.2f}")
    summary.append(f"  • Additional Revenue: RM {totals['total_additional_revenue']:,.2f}")
    if totals['total_additional_spend'] > 0:
        summary.append(f"  • Additional Spend: RM {totals['total_additional_spend']:,.2f}")
    summary.append(f"  • Net Monthly Benefit: RM {totals['total_net_benefit']:,.2f}")
    summary.append("")

    summary.append("📈 Conversion Impact:")
    summary.append(f"  • Additional Conversions: {totals['total_additional_conversions']:.1f}/month")
    summary.append("")

    summary.append("🤖 Automation Status:")
    summary.append(f"  • Auto-Actionable: {totals['automatable_count']}")
    summary.append(f"  • Manual Required: {totals['manual_count']}")
    summary.append("")

    summary.append("📊 Priority Breakdown:")
    for priority, count in sorted(totals['breakdown_by_priority'].items()):
        if count > 0:
            summary.append(f"  • {priority.upper()}: {count}")

    return "\n".join(summary)


def get_top_impact_recommendations(recommendations, limit=5):
    """
    Get top recommendations by net benefit.

    Args:
        recommendations: List of recommendation dicts
        limit: Number of top recommendations to return

    Returns:
        List of top recommendations sorted by net benefit
    """
    # Calculate net benefit for each recommendation
    scored_recs = []
    for rec in recommendations:
        impact_data = rec.get('impact_data', {})
        net_benefit = impact_data.get('net_benefit_monthly', 0)

        # If not provided, calculate from components
        if net_benefit == 0:
            monthly_savings = impact_data.get('monthly_savings', 0)
            additional_revenue = impact_data.get('additional_revenue_monthly', 0)
            additional_spend = impact_data.get('additional_spend_monthly', 0)
            net_benefit = monthly_savings + additional_revenue - additional_spend

        scored_recs.append((net_benefit, rec))

    # Sort by net benefit descending
    scored_recs.sort(key=lambda x: x[0], reverse=True)

    # Return top N
    return [rec for _, rec in scored_recs[:limit]]
