"""
AI-Powered Support Ticket Router
----------------------------------
1. Fetches mock support tickets from a public REST API (JSON)
2. Classifies each ticket with Claude when a valid Anthropic API key is available
3. Falls back to a mock rule-based classifier when no valid API key is available
4. Writes structured routing_decisions.json to output/
5. Power Automate watches that folder and sends Teams/email alerts

Requirements:
    pip install anthropic requests

Usage:
    export ANTHROPIC_API_KEY=your_key_here   # optional
    python ticket_router.py
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

try:
    import anthropic
except ImportError:
    anthropic = None

import requests

# ── Config ────────────────────────────────────────────────────────────────────

OUTPUT_DIR   = Path("output")
OUTPUT_FILE  = OUTPUT_DIR / "routing_decisions.json"
API_KEY      = os.environ.get("ANTHROPIC_API_KEY", "")

# JSONPlaceholder — free public REST API, returns posts we treat as tickets
TICKETS_API  = "https://jsonplaceholder.typicode.com/posts?_limit=10"

TEAMS = {
    "billing":      "billing-support@company.com",
    "technical":    "tech-support@company.com",
    "account":      "account-team@company.com",
    "general":      "helpdesk@company.com",
}


# ── Step 1 · Fetch tickets from REST API ─────────────────────────────────────

def fetch_tickets() -> list[dict]:
    print("📡  Fetching tickets from API...")
    response = requests.get(TICKETS_API, timeout=10)
    response.raise_for_status()
    raw = response.json()

    # Normalise JSONPlaceholder posts → ticket schema
    tickets = []
    for item in raw:
        tickets.append({
            "id":      item["id"],
            "subject": item["title"].capitalize(),
            "body":    item["body"],
            "source":  TICKETS_API,
        })

    print(f"   ✅  {len(tickets)} tickets fetched\n")
    return tickets


# ── Step 2 · Classify + route with Claude ────────────────────────────────────

SYSTEM_PROMPT = """
You are a support ticket classifier. Given a ticket, return ONLY a JSON object
with these exact keys — no extra text, no markdown fences:

{
  "urgency":   "low" | "medium" | "high",
  "category":  "billing" | "technical" | "account" | "general",
  "summary":   "One sentence (max 20 words) describing the issue.",
  "reasoning": "One sentence explaining the classification."
}

Base urgency on emotional tone and business impact.
Base category on the subject matter.
""".strip()


def mock_classify_ticket(ticket: dict) -> dict:
    text = f"{ticket['subject']} {ticket['body']}".lower()

    if any(word in text for word in ["bill", "payment", "charge", "refund"]):
        category = "billing"
    elif any(word in text for word in ["error", "bug", "crash", "technical", "issue"]):
        category = "technical"
    elif any(word in text for word in ["account", "login", "password", "username"]):
        category = "account"
    else:
        category = "general"

    if any(word in text for word in ["urgent", "immediately", "asap", "critical"]):
        urgency = "high"
    elif any(word in text for word in ["soon", "unable", "problem", "issue"]):
        urgency = "medium"
    else:
        urgency = "low"

    return {
        "urgency": urgency,
        "category": category,
        "summary": "Mock-classified support ticket for workflow demonstration.",
        "reasoning": "Used keyword-based fallback logic because no valid Anthropic API key was available.",
    }


def classify_ticket(client, ticket: dict) -> dict:
    if client is None:
        return mock_classify_ticket(ticket)

    user_message = f"Subject: {ticket['subject']}\n\n{ticket['body']}"

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()

    # Strip accidental markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    classification = json.loads(raw.strip())
    return classification


def route_ticket(ticket: dict, classification: dict) -> dict:
    team_email = TEAMS.get(classification["category"], TEAMS["general"])
    return {
        "ticket_id":   ticket["id"],
        "subject":     ticket["subject"],
        "urgency":     classification["urgency"],
        "category":    classification["category"],
        "summary":     classification["summary"],
        "reasoning":   classification["reasoning"],
        "routed_to":   team_email,
        "processed_at": datetime.utcnow().isoformat() + "Z",
    }


# ── Step 3 · Process all tickets ─────────────────────────────────────────────

def process_tickets(tickets: list[dict]) -> list[dict]:
    use_anthropic = bool(API_KEY) and anthropic is not None

    if use_anthropic:
        client = anthropic.Anthropic(api_key=API_KEY)
        print("🤖  Classifying tickets with Claude...\n")
    else:
        client = None
        print("🤖  No valid Anthropic API key detected — using mock AI classifier...\n")

    results = []

    for ticket in tickets:
        print(f"   Processing ticket #{ticket['id']}: {ticket['subject'][:50]}...")
        try:
            classification = classify_ticket(client, ticket)
            decision = route_ticket(ticket, classification)
            results.append(decision)

            urgency_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(
                decision["urgency"], "⚪"
            )
            print(
                f"   {urgency_icon} [{decision['urgency'].upper():6}] "
                f"{decision['category']:10} → {decision['routed_to']}"
            )
            time.sleep(0.3)

        except Exception as e:
            print(f"   ⚠️  Failed to process ticket #{ticket['id']}: {e}")
            results.append({
                "ticket_id": ticket["id"],
                "subject": ticket["subject"],
                "urgency": "unknown",
                "category": "general",
                "summary": "Classification failed — needs manual review.",
                "reasoning": str(e),
                "routed_to": TEAMS["general"],
                "processed_at": datetime.utcnow().isoformat() + "Z",
            })

    return results


# ── Step 4 · Write JSON output (Power Automate watches this file) ─────────────

def save_results(results: list[dict]):
    OUTPUT_DIR.mkdir(exist_ok=True)
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "ticket_count": len(results),
        "tickets":      results,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2))
    print(f"\n✅  Routing decisions saved → {OUTPUT_FILE}")
    print("   Power Automate trigger: watch this file for new drops.\n")


# ── Summary print ─────────────────────────────────────────────────────────────

def print_summary(results: list[dict]):
    from collections import Counter
    urgency_counts  = Counter(r["urgency"]  for r in results)
    category_counts = Counter(r["category"] for r in results)

    print("─" * 48)
    print("  ROUTING SUMMARY")
    print("─" * 48)
    print(f"  Total tickets processed : {len(results)}")
    print(f"  🔴 High urgency         : {urgency_counts.get('high', 0)}")
    print(f"  🟡 Medium urgency       : {urgency_counts.get('medium', 0)}")
    print(f"  🟢 Low urgency          : {urgency_counts.get('low', 0)}")
    print()
    for cat, count in category_counts.most_common():
        print(f"  {cat.capitalize():12} → {count} ticket(s) → {TEAMS[cat]}")
    print("─" * 48)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    tickets = fetch_tickets()
    results = process_tickets(tickets)
    save_results(results)
    print_summary(results)


if __name__ == "__main__":
    main()
