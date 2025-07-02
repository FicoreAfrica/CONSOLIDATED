# ficore-accounting Repository Structure

```
ficore-accounting/
├── admin/
│   ├── __init__.py
│   └── routes.py
├── agents/
│   ├── __init__.py
│   └── routes.py
├── coins/
│   ├── __init__.py
│   └── routes.py
├── common_features/
│   ├── __init__.py
│   ├── routes.py
│   └── taxation.py
├── creditors/
│   ├── __init__.py
│   └── routes.py
├── dashboard/
│   └── routes.py
├── debtors/
│   ├── __init__.py
│   └── routes.py
├── general/
│   └── routes.py
├── inventory/
│   ├── __init__.py
│   └── routes.py
├── payments/
│   ├── __init__.py
│   └── routes.py
├── personal/
│   ├── __init__.py
│   ├── bill.py
│   ├── budget.py
│   ├── emergency_fund.py
│   ├── financial_health.py
│   ├── learning_hub.py
│   ├── net_worth.py
│   └── quiz.py
├── receipts/
│   ├── __init__.py
│   └── routes.py
├── reports/
│   ├── __init__.py
│   └── routes.py
├── settings/
│   ├── __init__.py
│   └── routes.py
├── static/
│   ├── css/
│   │   └── styles.css
│   ├── icons/
│   ├── img/
│   ├── js/
│   ├── manifest.json
│   ├── service-worker.js
│   ├── site.webmanifest
│   └── sw.js
├── static_personal/
├── templates/
│   ├── admin/
│   │   ├── audit.html
│   │   ├── coins_credit.html
│   │   ├── dashboard.html
│   │   ├── manage_agents.html
│   │   ├── reset.html
│   │   └── users.html
│   ├── agents/
│   │   └── agent_portal.html
│   ├── coins/
│   │   ├── history.html
│   │   ├── purchase.html
│   │   └── receipt_upload.html
│   ├── common_features/
│   │   └── taxation/
│   │       └── news.html
│   ├── creditors/
│   │   ├── add.html
│   │   ├── edit.html
│   │   ├── index.html
│   │   └── view.html
│   ├── dashboard/
│   │   └── index.html
│   ├── debtors/
│   │   ├── add.html
│   │   ├── edit.html
│   │   ├── index.html
│   │   └── view.html
│   ├── errors/
│   │   ├── 403.html
│   │   ├── 404.html
│   │   └── 500.html
│   ├── general/
│   │   ├── Infographic_ficore.html
│   │   ├── about.html
│   │   ├── contact.html
│   │   ├── feedback.html
│   │   ├── home.html
│   │   ├── privacy.html
│   │   └── terms.html
│   ├── inventory/
│   │   ├── add.html
│   │   ├── edit.html
│   │   ├── index.html
│   │   └── low_stock.html
│   ├── payments/
│   │   ├── add.html
│   │   ├── edit.html
│   │   └── index.html
│   ├── personal/
│   │   ├── BILL/
│   │   │   ├── bill_main.html
│   │   │   ├── bill_reminder.html
│   │   │   └── bill_reminder_gmail.html
│   │   ├── BUDGET/
│   │   │   ├── budget_email.html
│   │   │   ├── budget_email_gmail.html
│   │   │   └── budget_main.html
│   │   ├── EMERGENCYFUND/
│   │   │   ├── emergency_fund_email.html
│   │   │   ├── emergency_fund_email_gmail.html
│   │   │   └── emergency_fund_main.html
│   │   ├── GENERAL/
│   │   │   ├── 404.html
│   │   │   ├── 500.html
│   │   │   ├── about.html
│   │   │   ├── admin_dashboard.html
│   │   │   ├── error.html
│   │   │   ├── feedback.html
│   │   │   ├── forgot_password.html
│   │   │   ├── general_dashboard.html
│   │   │   ├── index.html
│   │   │   ├── profile.html
│   │   │   ├── reset_password.html
│   │   │   ├── signin.html
│   │   │   ├── signup.html
│   │   │   ├── tool_header.html
│   │   │   └── view_edit_bills.html
│   │   ├── HEALTHSCORE/
│   │   │   ├── health_score_email.html
│   │   │   ├── health_score_email_gmail.html
│   │   │   └── health_score_main.html
│   │   ├── LEARNINGHUB/
│   │   │   └── learning_hub_main.html
│   │   ├── NETWORTH/
│   │   │   ├── net_worth_email.html
│   │   │   ├── net_worth_email_gmail.html
│   │   │   └── net_worth_main.html
│   │   ├── QUIZ/
│   │   │   ├── quiz_email.html
│   │   │   ├── quiz_email_gmail.html
│   │   │   └── quiz_main.html
│   │   ├── base.html
│   │   └── tool_header.html
│   ├── receipts/
│   │   ├── add.html
│   │   ├── edit.html
│   │   └── index.html
│   ├── reports/
│   │   ├── index.html
│   │   ├── inventory.html
│   │   └── profit_loss.html
│   ├── settings/
│   │   ├── index.html
│   │   ├── language.html
│   │   ├── notifications.html
│   │   └── profile.html
│   ├── users/
│   │   ├── agent_setup.html
│   │   ├── forgot_password.html
│   │   ├── login.html
│   │   ├── personal_setup.html
│   │   ├── reset_password.html
│   │   ├── setup.html
│   │   ├── signin.html
│   │   └── signup.html
│   └── base.html
├── translations/
│   ├── accounting_tools/
│   │   ├── __init__.py
│   │   ├── admin_translations.py
│   │   ├── agents_translations.py
│   │   ├── coins_translations.py
│   │   ├── creditors_translations.py
│   │   ├── debtors_translations.py
│   │   ├── inventory_translations.py
│   │   ├── payments_translations.py
│   │   ├── receipts_translations.py
│   │   └── reports_translations.py
│   ├── general_tools/
│   │   ├── __init__.py
│   │   ├── common_features_translations.py
│   │   └── general_translations.py
│   ├── personal_finance/
│   │   ├── __init__.py
│   │   ├── bill_translations.py
│   │   ├── budget_translations.py
│   │   ├── emergency_fund_translations.py
│   │   ├── financial_health_translations.py
│   │   ├── learning_hub_translations.py
│   │   ├── net_worth_translations.py
│   │   └── quiz_translations.py
│   └── __init__.py
├── users/
│   ├── __init__.py
│   └── routes.py
├── __init__.py
├── app.py
├── mailersend_email.py
├── models.py
├── requirements.txt
├── scheduler_setup.py
├── session_utils.py
├── utils.py
├── wsgi.py
└── .gitignore
```