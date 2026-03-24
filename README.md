# AI-Powered Support Ticket Router

An end-to-end automation pipeline that fetches support tickets from a REST API, uses Claude (Anthropic) to classify urgency and category, routes tickets to the appropriate team, and triggers Power Automate alerts — eliminating manual triage.

---

## 🚀 Overview

This project simulates a real-world enterprise workflow where incoming support tickets are:

1. Ingested from a REST API  
2. Processed and normalized (JSON)  
3. Classified using AI (Claude)  
4. Routed to the correct team  
5. Triggered into an automated alert workflow (Power Automate)  

The goal is to reduce manual effort, improve routing consistency, and create a scalable workflow for handling support requests.

---

## ⚙️ Tech Stack

- Python  
- REST API (JSONPlaceholder)  
- JSON Processing  
- Claude (Anthropic API)  
- Power Automate (workflow automation)  

---

## 🔄 Workflow

**Data Ingestion → AI Classification → Routing → Automation → Alerts**

- Fetch tickets via REST API  
- Send ticket content to Claude for:
  - urgency classification  
  - category detection  
  - summary generation  
- Output structured `routing_decisions.json`  
- Power Automate watches output and sends alerts  

---

## 🛡️ Reliability & Edge Handling

- Fallback routing for failed classifications  
- Default assignment to general support when errors occur  
- Rate limiting to avoid API overuse  
- Structured outputs for downstream systems  
- High-urgency tickets can be flagged for manual review (human-in-the-loop)

This ensures the system remains stable, reliable, and usable in real-world environments.

---

## 📊 Example Output

Each ticket is processed into structured JSON:

```json
{
  "ticket_id": 1,
  "urgency": "high",
  "category": "technical",
  "summary": "User cannot access account",
  "routed_to": "tech-support@company.com"
}
