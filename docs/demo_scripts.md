# Hackathon Demo Scripts (Person D)

## 5-MINUTE JUDGE DEMO SCRIPT
*(Target: consistently under 4:45. Extra 15s is for questions)*

**0:00–0:20 — Value prop**
"We built DataForge. A business user describes what they want in plain English. DataForge generates a governance-compliant data application in 60 seconds — security, audit trails, and AI insights built in. No engineering required."

**0:20–1:30 — Governance proof (MOST CRITICAL)**
Open Page 2. Point to the email column: "PII is masked at the Unity Catalog level — the app never sees raw email addresses. Enforced in catalog, not the app." 
Open sidebar, switch Data Scope to "West Only." Data changes. Switch to "East Only."
"Role-based data scoping through parameterized governed views. App has zero access to raw tables — I can show you the permission denied right now."

**1:30–2:30 — Dashboard**
"Five live KPIs. Three interactive Plotly charts. One date filter updates everything simultaneously." 
Change the date range. Watch charts update. "A non-technical user explores without writing SQL."

**2:30–3:45 — Chat**
Go to Page 3. Click example question button. 
Open SQL expander: "Actual SQL AI generated — governed views only, always has LIMIT, SELECT only. Guardrails enforced at generation." 
Show AI Briefing card: "Claude interpreted the result in English."
*(If self-healing fired, point to "Query auto-corrected" badge.)*

**3:45–4:30 — Factory**
Go to Page 1. 
Type: "inventory dashboard by warehouse with supplier filter." Hit Generate. Watch progress feed. Dashboard renders inline. 
Open code expander: "That's the Python DataForge wrote. Governance validated. You could deploy this anywhere."
**(FALLBACK: If factory LLM fails, show spec validator output — type description, show JSON spec, show governance validation removing disallowed tables with reasons, show generated code in expander.)**

**4:30–5:00 — Audit console**
Go to Page 5. Hit Refresh. "Every query, every role, every AI decision — logged. IT has complete visibility. Nothing happens without a trace."
Close: "We didn't build a dashboard. We built the factory that builds dashboards — with governance baked in from day one."

---

## 10-MINUTE SPONSOR BOOTH VERSION
*For Databricks reps and Koch judges.* Add these 5 minutes:

- Open Databricks catalog UI, show the column mask policy on the email column definition (1 min)
- Show permission denied when querying raw.sales directly in a notebook tab (30 sec)
- Open `guardrails.yaml` and `roles.yaml` in editor: "these are read at runtime by every agent and the factory — active config, not documentation" (1 min)
- Open `steering_doc.md`: "our steering document, the template that defines how the factory interprets business user intent" (30 sec)
- Page 4: click "Analyze My Data," show 5 suggestions appear from schema analysis, click "Build This" — factory pre-fills with the suggestion prompt (1 min)
- Admin console: walk through a self-heal diff in detail (1 min)
- Show generated code in full, explain Jinja2 template approach (1 min)
