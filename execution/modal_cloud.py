#!/usr/bin/env python3
"""
Modal Cloud Deployment for Ad Optimization Reports
Automatically generates and emails weekly reports for all clients.

Testing Mode: All reports sent to andrea@autoflow-solutions.com
Production Mode: Reports sent to client emails in database

Schedule: Every Monday 8 AM Malaysia Time (GMT+8)
"""

import modal
from datetime import datetime, timedelta
import json
import os
import sys
import base64
from pathlib import Path

# ============================================================================
# MODAL APP CONFIGURATION
# ============================================================================

app = modal.App("ad-optimization-reports")

# Persistent volume for client database
volume = modal.Volume.from_name("client-data", create_if_missing=True)

# Project root for loading local files
project_root = Path(__file__).parent.parent

# Modal image with all dependencies - using direct pip_install to avoid Windows encoding issues
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "google-ads>=28.0.0",
        "facebook-business>=19.0.0",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
        "gspread>=6.0.0",
        "oauth2client>=4.1.3",
        "google-auth>=2.27.0",
        "google-auth-oauthlib>=1.2.0",
        "google-auth-httplib2>=0.2.0",
        "pandas>=2.2.0",
        "numpy>=1.26.0",
    )
    .add_local_file(project_root / "execution" / "fetch_google_ads_metrics.py", "/root/fetch_google_ads_metrics.py")
    .add_local_file(project_root / "execution" / "fetch_facebook_ads_metrics.py", "/root/fetch_facebook_ads_metrics.py")
    .add_local_file(project_root / "execution" / "create_full_insights.py", "/root/create_full_insights.py")
    .add_local_file(project_root / "execution" / "create_facebook_insights.py", "/root/create_facebook_insights.py")
    .add_local_file(project_root / "execution" / "create_html_dashboard.py", "/root/create_html_dashboard.py")
    .add_local_file(project_root / "execution" / "create_facebook_html_dashboard.py", "/root/create_facebook_html_dashboard.py")
    .add_local_file(project_root / "execution" / "analyze_week2_insights.py", "/root/analyze_week2_insights.py")
    .add_local_file(project_root / "execution" / "analyze_advanced_insights.py", "/root/analyze_advanced_insights.py")
    .add_local_file(project_root / "execution" / "analyze_facebook_insights.py", "/root/analyze_facebook_insights.py")
    .add_local_file(project_root / "execution" / "utils.py", "/root/utils.py")
    .add_local_file(project_root / "clients.json", "/root/clients.json")
)

# Testing mode - send all emails to this address
TESTING_MODE = True
TEST_EMAIL = "andrea@autoflow-solutions.com"

# ============================================================================
# HELPER: SEND ERROR EMAIL (non-Modal function, used inside scheduled job)
# ============================================================================

def send_error_email(error_message: str):
    """Send a simple error notification email to the admin."""
    import smtplib
    from email.mime.text import MIMEText

    admin_email = TEST_EMAIL
    smtp_user = os.getenv('SMTP_USER')
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = os.getenv('SMTP_PORT')
    smtp_password = os.getenv('SMTP_PASSWORD')

    if not all([smtp_user, smtp_host, smtp_port, smtp_password]):
        print(f"⚠️  Cannot send error email - SMTP not configured. Error: {error_message}")
        return

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #ea4335;">❌ Weekly Report Job - Critical Error</h2>
        <p>{error_message}</p>
        <p><em>Time: {datetime.now().isoformat()}</em></p>
        <p><em>Check Modal logs for more details.</em></p>
    </body>
    </html>
    """

    msg = MIMEText(body, 'html')
    msg['From'] = smtp_user
    msg['To'] = admin_email
    msg['Subject'] = f"❌ Weekly Report - Critical Error"

    try:
        with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(f"✅ Error notification sent to {admin_email}")
    except Exception as e:
        print(f"⚠️  Failed to send error email: {e}")


# ============================================================================
# SCHEDULED JOB - MAIN ORCHESTRATOR
# ============================================================================

@app.function(
    schedule=modal.Cron("0 0 * * MON"),  # Monday midnight UTC = 8 AM GMT+8
    image=image,
    secrets=[
        modal.Secret.from_name("google-ads-creds"),
        modal.Secret.from_name("facebook-ads-creds"),
        modal.Secret.from_name("smtp-creds"),
        modal.Secret.from_name("google-credentials"),
    ],
    volumes={"/data": volume},
    timeout=1800,  # 30 minutes
)
def weekly_report_job():
    """
    Main scheduler - loads all clients and spawns parallel report generation.
    Runs every Monday at 8 AM Malaysia Time (GMT+8).
    """
    print(f"\n{'='*80}")
    print(f"WEEKLY REPORT JOB STARTED")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Testing Mode: {TESTING_MODE}")
    print(f"{'='*80}\n")

    # Load clients from persistent volume, fall back to image-bundled copy
    clients_file = Path("/data/clients.json")
    bundled_file = Path("/root/clients.json")

    if not clients_file.exists():
        if bundled_file.exists():
            print("⚠️  No clients.json in volume, using bundled copy...")
            import shutil
            shutil.copy2(str(bundled_file), str(clients_file))
            volume.commit()
            print("✓ Copied bundled clients.json to volume for future runs")
        else:
            print("❌ ERROR: No clients.json found in volume or image")
            send_error_email("No clients.json found in Modal volume or image")
            return

    with open(clients_file) as f:
        clients = json.load(f)

    if not clients:
        print("⚠️  WARNING: clients.json is empty")
        send_error_email("clients.json exists but contains no clients")
        return

    print(f"📋 Found {len(clients)} clients in database\n")

    # Track results
    results = []

    # Spawn parallel report generation for each client
    for client_name, client_data in clients.items():
        customer_id = client_data.get('customer_id')
        facebook_ad_account_id = client_data.get('facebook_ad_account_id')

        # In testing mode, override email
        if TESTING_MODE:
            email = TEST_EMAIL
            print(f"🧪 [TEST MODE] {client_name} → {email}")
        else:
            email = client_data.get('email')
            if not email:
                print(f"⚠️  WARNING: No email for {client_name}, skipping...")
                results.append({
                    'client': client_name,
                    'status': 'skipped',
                    'reason': 'No email address'
                })
                continue

        # Spawn async report generation
        result = generate_client_report.spawn(
            client_name=client_name,
            customer_id=customer_id,
            facebook_ad_account_id=facebook_ad_account_id,
            email=email
        )
        results.append({'client': client_name, 'result': result})

    # Wait for all reports to complete
    print(f"\n⏳ Waiting for {len(results)} reports to complete...\n")

    errors = []
    successes = []

    for item in results:
        if 'result' not in item:  # Skipped clients
            continue

        try:
            item['result'].get()  # Block until complete
            successes.append(item['client'])
            print(f"✅ {item['client']} - Report sent successfully")
        except Exception as e:
            errors.append({'client': item['client'], 'error': str(e)})
            print(f"❌ {item['client']} - Failed: {str(e)}")

    # Summary
    print(f"\n{'='*80}")
    print(f"WEEKLY REPORT JOB COMPLETED")
    print(f"Successes: {len(successes)}")
    print(f"Failures: {len(errors)}")
    print(f"{'='*80}\n")

    # Send error summary if any failures
    if errors:
        send_error_summary.remote(errors, successes)


# ============================================================================
# CREDENTIAL SETUP
# ============================================================================

def setup_credentials():
    """Reconstruct credentials.json from Base64 environment variable"""
    print("Setting up credentials...")

    # Reconstruct Google OAuth credentials for Sheets API
    google_creds_base64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')
    if google_creds_base64:
        try:
            with open('/root/credentials.json', 'wb') as f:
                f.write(base64.b64decode(google_creds_base64))
            print("✓ credentials.json reconstructed")
        except Exception as e:
            print(f"⚠ Failed to reconstruct credentials.json: {e}")
    else:
        print("⚠ GOOGLE_CREDENTIALS_BASE64 not found in environment")

    # Reconstruct token.json if provided (for pre-authenticated OAuth)
    google_token_base64 = os.getenv('GOOGLE_TOKEN_BASE64')
    if google_token_base64:
        try:
            with open('/root/token.json', 'wb') as f:
                f.write(base64.b64decode(google_token_base64))
            print("✓ token.json reconstructed")
        except Exception as e:
            print(f"⚠ Failed to reconstruct token.json: {e}")

# ============================================================================
# REPORT GENERATION - PER CLIENT
# ============================================================================

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("google-ads-creds"),
        modal.Secret.from_name("facebook-ads-creds"),
        modal.Secret.from_name("smtp-creds"),
        modal.Secret.from_name("google-credentials"),
    ],
    timeout=600,  # 10 minutes per client
)
def generate_client_report(
    client_name: str,
    customer_id: str = None,
    facebook_ad_account_id: str = None,
    email: str = None
):
    """
    Generate and email weekly report for a single client.
    Handles both Google Ads and Facebook Ads.
    """
    print(f"\n{'='*60}")
    print(f"Generating report for: {client_name}")
    print(f"Google Ads: {'✓' if customer_id else '✗'}")
    print(f"Facebook Ads: {'✓' if facebook_ad_account_id else '✗'}")
    print(f"{'='*60}\n")

    # Setup credentials (reconstruct files from Base64 env vars)
    setup_credentials()

    # Date range: last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    dashboards = []  # List of (filename, html_content) tuples
    summary = {}
    errors = []

    # Add execution scripts to path
    sys.path.insert(0, '/root')

    # ========================================================================
    # GOOGLE ADS REPORT
    # ========================================================================
    if customer_id:
        try:
            print(f"📊 Fetching Google Ads metrics...")

            # Import existing scripts
            import fetch_google_ads_metrics
            import create_full_insights
            import create_html_dashboard

            # Fetch metrics (writes to /tmp/) - Set sys.argv for argparse
            sys.argv = [
                'fetch_google_ads_metrics',
                '--customer_id', customer_id,
                '--start_date', start_date.strftime('%Y-%m-%d'),
                '--end_date', end_date.strftime('%Y-%m-%d'),
                '--output_dir', '/tmp'
            ]
            metrics_file = fetch_google_ads_metrics.main()
            print(f"   ✓ Metrics saved: {metrics_file}")

            # Create insights - Call function directly
            customer_id_str = customer_id.replace('-', '')
            insights_file = f"/tmp/insights_enhanced_{customer_id_str}.json"
            recs_file = f"/tmp/recommendations_enhanced_{customer_id_str}.json"

            create_full_insights.create_enhanced_insights(metrics_file, insights_file, recs_file)
            print(f"   ✓ Insights saved: {insights_file}")

            # Generate HTML dashboard - Set sys.argv for argparse
            sys.argv = [
                'create_html_dashboard',
                '--metrics_file', metrics_file,
                '--insights_file', insights_file,
                '--recommendations_file', recs_file,
                '--output_file', f"/tmp/google_ads_dashboard_{customer_id_str}.html"
            ]
            google_dashboard_path = f"/tmp/google_ads_dashboard_{customer_id_str}.html"
            create_html_dashboard.main()
            print(f"   ✓ Dashboard saved: {google_dashboard_path}")

            # Read HTML content
            with open(google_dashboard_path, 'r') as f:
                html_content = f.read()

            dashboards.append((
                f"Google_Ads_Report_{client_name.replace(' ', '_')}.html",
                html_content
            ))

            # Extract summary metrics for email - use metrics file which has known structure
            with open(metrics_file, 'r') as f:
                metrics_data = json.load(f)
                metrics_summary = metrics_data.get('summary', {}) if isinstance(metrics_data, dict) else {}
                summary['google_spend'] = metrics_summary.get('total_cost', 0)
                summary['google_conversions'] = metrics_summary.get('total_conversions', 0)

            print(f"✅ Google Ads report generated successfully")

        except (Exception, SystemExit) as e:
            import traceback
            error_msg = f"Google Ads error: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"Full traceback:\n{traceback.format_exc()}")
            errors.append(error_msg)

    # ========================================================================
    # FACEBOOK ADS REPORT
    # ========================================================================
    if facebook_ad_account_id:
        try:
            print(f"📊 Fetching Facebook Ads metrics...")

            import fetch_facebook_ads_metrics
            import create_facebook_insights
            import create_facebook_html_dashboard

            # Fetch metrics - Set sys.argv for argparse
            sys.argv = [
                'fetch_facebook_ads_metrics',
                '--ad_account_id', facebook_ad_account_id,
                '--start_date', start_date.strftime('%Y-%m-%d'),
                '--end_date', end_date.strftime('%Y-%m-%d'),
                '--output_dir', '/tmp'
            ]
            metrics_file = fetch_facebook_ads_metrics.main()
            print(f"   ✓ Metrics saved: {metrics_file}")

            # Create insights - use proper --flag format
            sys.argv = [
                'create_facebook_insights',
                '--metrics_file', metrics_file,
                '--output_dir', '/tmp'
            ]
            insights_file, fb_recs_file = create_facebook_insights.main()
            print(f"   ✓ Insights saved: {insights_file}")

            # Generate HTML dashboard - use proper --flag format
            sys.argv = [
                'create_facebook_html_dashboard',
                '--metrics_file', metrics_file,
                '--insights_file', insights_file,
                '--recommendations_file', fb_recs_file,
                '--output_dir', '/tmp'
            ]
            create_facebook_html_dashboard.main()

            # Find the generated dashboard file (main() may return None)
            import glob
            fb_dashboard_files = glob.glob(f"/tmp/facebook_ads_dashboard_*.html")
            if fb_dashboard_files:
                fb_dashboard_path = sorted(fb_dashboard_files)[-1]  # Most recent
            else:
                raise Exception("Facebook dashboard HTML file not found in /tmp/")
            print(f"   ✓ Dashboard saved: {fb_dashboard_path}")

            # Read HTML content
            with open(fb_dashboard_path, 'r') as f:
                html_content = f.read()

            dashboards.append((
                f"Facebook_Ads_Report_{client_name.replace(' ', '_')}.html",
                html_content
            ))

            # Extract summary metrics - use metrics file which has known structure
            with open(metrics_file, 'r') as f:
                fb_metrics_data = json.load(f)
                fb_summary = fb_metrics_data.get('summary', {}) if isinstance(fb_metrics_data, dict) else {}
                summary['facebook_spend'] = fb_summary.get('total_spend', 0)
                summary['facebook_conversions'] = fb_summary.get('total_conversions', 0)

            print(f"✅ Facebook Ads report generated successfully")

        except (Exception, SystemExit) as e:
            import traceback
            error_msg = f"Facebook Ads error: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"Full traceback:\n{traceback.format_exc()}")
            errors.append(error_msg)

    # ========================================================================
    # SEND EMAIL
    # ========================================================================
    if dashboards:
        try:
            send_email_report.remote(
                client_name=client_name,
                email=email,
                dashboards=dashboards,
                summary=summary,
                errors=errors,
                date_range=(start_date, end_date)
            )
            print(f"✅ Email sent to {email}")
        except Exception as e:
            print(f"❌ Email sending failed: {str(e)}")
            raise
    else:
        raise Exception("No dashboards generated - both Google and Facebook failed")


# ============================================================================
# EMAIL SENDING
# ============================================================================

@app.function(
    secrets=[modal.Secret.from_name("smtp-creds")]
)
def send_email_report(
    client_name: str,
    email: str,
    dashboards: list,
    summary: dict,
    errors: list,
    date_range: tuple
):
    """Send email with HTML dashboard attachments."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.application import MIMEApplication

    start_date, end_date = date_range

    # Calculate totals (round conversions to int - Google Ads API returns floats)
    total_spend = summary.get('google_spend', 0) + summary.get('facebook_spend', 0)
    total_conv = int(round(summary.get('google_conversions', 0) + summary.get('facebook_conversions', 0)))
    avg_cpa = total_spend / total_conv if total_conv > 0 else 0

    # Compose email
    msg = MIMEMultipart()
    msg['From'] = os.getenv('SMTP_USER')
    msg['To'] = email

    # Subject line (with [TEST] prefix in testing mode)
    subject_prefix = "[TEST] " if TESTING_MODE else ""
    msg['Subject'] = f"{subject_prefix}Weekly Ad Performance Report - {client_name}"

    # Email body HTML
    errors_html = ""
    if errors:
        errors_html = f"""
        <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
            <h3 style="color: #856404; margin-top: 0;">⚠️ Partial Report</h3>
            <p style="color: #856404; margin: 0;">Some data could not be retrieved:</p>
            <ul style="color: #856404;">
                {''.join(f'<li>{err}</li>' for err in errors)}
            </ul>
        </div>
        """

    body = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f5f5f5;">
        <div style="max-width: 600px; margin: 40px auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">

            <!-- Header -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">📊 Weekly Performance Report</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 14px;">
                    {start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}
                </p>
            </div>

            <!-- Content -->
            <div style="padding: 30px;">
                <h2 style="color: #333; margin-top: 0;">Hello {client_name},</h2>
                <p style="color: #666; line-height: 1.6;">
                    Your weekly ad performance report is ready. Here's a quick summary of the last 7 days:
                </p>

                {errors_html}

                <!-- Metrics Cards -->
                <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 25px 0;">
                    <div style="margin-bottom: 15px;">
                        <span style="color: #666; font-size: 14px;">Total Ad Spend</span>
                        <div style="color: #1a73e8; font-size: 28px; font-weight: bold;">
                            RM {total_spend:,.2f}
                        </div>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <span style="color: #666; font-size: 14px;">Total Conversions</span>
                        <div style="color: #34a853; font-size: 28px; font-weight: bold;">
                            {total_conv:,}
                        </div>
                    </div>
                    <div>
                        <span style="color: #666; font-size: 14px;">Average Cost Per Acquisition</span>
                        <div style="color: #ea4335; font-size: 28px; font-weight: bold;">
                            RM {avg_cpa:.2f}
                        </div>
                    </div>
                </div>

                <p style="color: #666; line-height: 1.6; margin-bottom: 15px;">
                    📎 <strong>Detailed analysis and optimization recommendations</strong> are attached to this email.
                </p>

                <!-- CTA Box -->
                <div style="background: #e8f0fe; border-radius: 8px; padding: 20px; margin: 25px 0;">
                    <h3 style="color: #1967d2; margin-top: 0; font-size: 16px;">📋 Next Steps</h3>
                    <p style="color: #5f6368; margin: 0; font-size: 14px; line-height: 1.6;">
                        Review the attached dashboards and let us know which optimization recommendations
                        you'd like to implement. Simply reply to this email with the recommendation numbers
                        you want to approve.
                    </p>
                </div>

                <p style="color: #666; line-height: 1.6; margin-top: 30px;">
                    Best regards,<br>
                    <strong style="color: #333;">Your Ad Optimization Team</strong>
                </p>
            </div>

            <!-- Footer -->
            <div style="background: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #e0e0e0;">
                <p style="color: #999; font-size: 12px; margin: 0;">
                    This is an automated report generated every Monday at 8 AM (GMT+8)
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(body, 'html'))

    # Attach HTML dashboards
    for filename, html_content in dashboards:
        attachment = MIMEApplication(html_content.encode('utf-8'), _subtype='html')
        attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(attachment)

    # Send via SMTP
    try:
        with smtplib.SMTP(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT'))) as server:
            server.starttls()
            server.login(os.getenv('SMTP_USER'), os.getenv('SMTP_PASSWORD'))
            server.send_message(msg)

        print(f"✅ Email sent successfully to {email}")
    except Exception as e:
        print(f"❌ SMTP error: {str(e)}")
        raise


# ============================================================================
# ERROR NOTIFICATION
# ============================================================================

@app.function(
    secrets=[modal.Secret.from_name("smtp-creds")]
)
def send_error_summary(errors: list, successes: list):
    """Send error summary email to admin."""
    import smtplib
    from email.mime.text import MIMEText

    admin_email = TEST_EMAIL  # andrea@autoflow-solutions.com

    errors_html = ''.join(f"<li><strong>{e['client']}</strong>: {e['error']}</li>" for e in errors)
    successes_html = ''.join(f"<li>{name}</li>" for name in successes)

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #ea4335;">⚠️ Weekly Report Job - Errors Detected</h2>
        <p>The weekly report job completed with some errors:</p>

        <h3 style="color: #34a853;">Successful Reports ({len(successes)})</h3>
        <ul>{successes_html}</ul>

        <h3 style="color: #ea4335;">Failed Reports ({len(errors)})</h3>
        <ul>{errors_html}</ul>

        <p><em>Check Modal logs for detailed error traces.</em></p>
    </body>
    </html>
    """

    msg = MIMEText(body, 'html')
    msg['From'] = os.getenv('SMTP_USER')
    msg['To'] = admin_email
    msg['Subject'] = f"⚠️ Weekly Report Errors - {len(errors)} Failed"

    with smtplib.SMTP(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT'))) as server:
        server.starttls()
        server.login(os.getenv('SMTP_USER'), os.getenv('SMTP_PASSWORD'))
        server.send_message(msg)

    print(f"✅ Error summary sent to {admin_email}")


# ============================================================================
# CLI COMMANDS (for manual testing)
# ============================================================================

@app.local_entrypoint()
def test_single_client(client_name: str = "YAP CHAN KOR"):
    """Test report generation for a single client (run locally)."""
    print(f"Testing report generation for: {client_name}")

    # Load client data
    import json
    with open('.tmp/clients.json') as f:
        clients = json.load(f)

    client_data = clients.get(client_name)
    if not client_data:
        print(f"❌ Client not found: {client_name}")
        return

    # Generate report
    generate_client_report.remote(
        client_name=client_name,
        customer_id=client_data.get('customer_id'),
        facebook_ad_account_id=client_data.get('facebook_ad_account_id'),
        email=TEST_EMAIL
    )

    print(f"✅ Test complete - check {TEST_EMAIL} for report")


# ============================================================================
# SYNC CLIENTS TO VOLUME
# ============================================================================

@app.function(
    image=image,
    volumes={"/data": volume},
)
def sync_clients_to_volume():
    """Copy the bundled clients.json into the persistent volume."""
    import shutil
    bundled = Path("/root/clients.json")
    target = Path("/data/clients.json")

    if not bundled.exists():
        print("❌ No clients.json bundled in image")
        return

    shutil.copy2(str(bundled), str(target))
    volume.commit()

    with open(target) as f:
        clients = json.load(f)
    print(f"✅ Synced clients.json to volume ({len(clients)} clients)")
