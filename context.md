# Context

HigherDOSE is a company that sells health and wellness electronic devices, beauty topicals, and supplements. The business operates in the beauty and supplement space, with a focus on both physical products and performance reporting.

## Roles & Workflow
- **Account Manager (You):** Acts as the intermediary between the CMO and external agencies/vendors. Responsible for compiling reports, communicating updates, and contextualizing channel performance for the CMO.
- **CMO:** Sets high-level growth initiatives and goals (e.g., 25% month-over-month or year-over-year growth). Relies on the account manager to minimize direct contact with vendors and to receive clear, actionable updates.
- **Agencies/Vendors:** Manage advertising channels (e.g., Meta/Facebook, Google). The account manager communicates with them, tracks deliverables, and ensures alignment with company goals.
- **Internal Team:** Includes finance/tech/HR multi-hat roles and other team members met during onboarding. Relationships and responsibilities may be tracked in a CRM-like fashion for context.

## Main Responsibilities
- Compile and deliver weekly and daily performance reports (especially for the CMO).
- Track and communicate wins, challenges, opportunities, and solutions.
- Monitor and analyze channel performance (Meta, Google, etc.), including year-over-year and week-over-week comparisons.
- Act as the point of contact for agencies/vendors, ensuring deliverables and action items are met.
- Automate reporting and communication where possible to reduce manual busywork.
- Maintain context on people/roles (CRM), projects, and ongoing initiatives.

## Goals & Incentives
- Meet or exceed growth targets (e.g., 25% MoM/YoY growth).
- Achieve performance bonuses (e.g., 20% bonus for hitting annual targets).
- Streamline and automate as much of the reporting and communication process as possible.
- Build systems that could scale to multiple clients or roles in the future.

## Recurring Questions / Reporting Needs
- What happened in the last day or last 7 days in each primary channel? (Performance, activities, changes)
- What are the wins and updates for the last 7 days?
- What challenges have arisen, and what opportunities or solutions are available?
- What are the year-over-year and week-over-week performance metrics for Meta, Google, and other primary channels?
- What are the current priorities, task lists, and deliverables for the month?
- Who are the key people involved in each initiative, and what is their role/contact info? (CRM context)
- What projects or activities have I been involved in recently?

---

This context is grounded in the transcript from the repo setup and onboarding session. It is intended to guide future documentation, automation, and AI assistance for the HigherDOSE account management and reporting workflow.


# Chats

## 👤 Prompt

what would i need to put in this repo for you to build these things for me? if you created a python script for each of these tasks what would it need access to?

## 🤖 Response

I'll analyze what you'd need to provide for me to build these reporting and analytics tools. Let me first check your context file to understand more about your project and then break down the requirements for each task.
Read file: context.md

Based on your context, here's what you'd need to provide in the repo for me to build these reporting and analytics tools:

## **Required Data Sources & Access**

### **1. API Credentials & Access**
You'd need to provide (in a secure config file or environment variables):

```
/config/
├── credentials.env                 # Environment variables for API keys
├── api_config.yaml                # API endpoints and settings
└── notification_config.yaml       # Email/Slack notification settings
```

**Required API Access:**
- **Meta/Facebook Ads API**: Access token, app ID, app secret, ad account IDs
- **Google Ads API**: OAuth2 credentials, customer IDs, developer token
- **Google Analytics API**: Service account credentials or OAuth2 tokens
- **Email API**: SMTP credentials or service like SendGrid/Mailgun
- **Slack API**: Bot token for notifications (optional)

### **2. Historical Data & Baselines**
```
/data/
├── historical_performance.csv      # Past performance data for YoY analysis
├── growth_targets.yaml            # 25% MoM/YoY targets by channel
├── channel_configs.yaml           # Channel-specific settings and thresholds
└── baseline_metrics.json          # Starting points for comparisons
```

### **3. Business Configuration**
```
/config/
├── business_rules.yaml            # What constitutes "good" vs "bad" performance
├── reporting_schedule.yaml        # When to send reports (daily 9am, weekly Mon 8am)
├── alert_thresholds.yaml         # When to trigger alerts (20% drop, etc.)
└── stakeholder_contacts.yaml     # CMO email, notification preferences
```

## **What Each Python Script Would Need:**

### **1. Daily/Weekly Performance Reports (`reports/performance_reporter.py`)**
```python
# Would need access to:
- Meta Ads API (campaign performance, spend, ROAS)
- Google Ads API (search/display performance, keywords)
- Google Analytics API (website traffic, conversions)
- Email API (to send reports to CMO)
- Historical data for week-over-week comparisons
```

### **2. Channel Performance Tracker (`tracking/channel_tracker.py`)**
```python
# Would need access to:
- Meta/Facebook Ads API (real-time campaign data)
- Google Ads API (search performance, budget utilization)
- Database to store daily snapshots
- Configuration for what metrics to track
```

### **3. Year-over-Year Analysis (`analytics/yoy_analyzer.py`)**
```python
# Would need access to:
- Historical performance data (12+ months)
- Current API data from all channels
- Statistical analysis libraries
- Visualization tools for trend charts
```

### **4. Growth Monitoring Dashboard (`dashboard/growth_monitor.py`)**
```python
# Would need access to:
- Real-time API data from all channels
- Growth target configurations (25% MoM/YoY)
- Web framework (Flask/Streamlit) for dashboard
- Database for storing metrics over time
```

### **5. Performance Alerts (`alerts/performance_alerts.py`)**
```python
# Would need access to:
- All channel APIs for real-time monitoring
- Alert threshold configurations
- Notification systems (email, Slack)
- Logic for detecting significant changes
```

## **Repository Structure I'd Create:**

```
HigherDOSE/
├── scripts/
│   ├── reports/performance_reporter.py
│   ├── tracking/channel_tracker.py
│   ├── analytics/yoy_analyzer.py
│   ├── dashboard/growth_monitor.py
│   └── alerts/performance_alerts.py
├── config/
│   ├── credentials.env.example
│   ├── api_config.yaml
│   ├── business_rules.yaml
│   └── reporting_schedule.yaml
├── data/
│   ├── historical_performance.csv
│   └── templates/
├── utils/
│   ├── api_connectors.py
│   ├── data_processors.py
│   └── notification_handlers.py
└── requirements.txt
```

## **Next Steps:**

1. **Start with sample data**: Provide a CSV with 2-3 months of historical performance data
2. **API access**: Set up developer accounts for Meta and Google Ads APIs
3. **Define success metrics**: What specific KPIs matter most to the CMO?
4. **Notification preferences**: How should alerts be delivered?

Would you like me to start with a specific task? I'd recommend beginning with the **performance reporter** since it's foundational for the other tools.