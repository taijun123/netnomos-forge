# -*- coding: utf-8 -*-
"""Composite state for the office demo.

The office UI needs product-domain objects, while the frozen backend contract
already exposes rules, cards, dual reports, jobs, and workflow events. This
module bridges the two without changing forge.contracts.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from forge.contracts import RuleCard, RuleSet, WorkflowEvent

AGENTS: list[dict[str, Any]] = [
    {
        "id": "supervisor",
        "agentCode": "A",
        "code": "A",
        "name": "Supervisor A",
        "role": "Workflow supervisor",
        "status": "running",
        "description": "Coordinates rule intake, data delivery, validation, packaging, and PM chat.",
        "color": "#1677ff",
        "accessory": "badge",
    },
    {
        "id": "courier",
        "agentCode": "B",
        "code": "B",
        "name": "Courier B",
        "role": "Data intake courier",
        "status": "running",
        "description": "Registers finance CSV, NetFlow CSV, and upload metadata for downstream agents.",
        "color": "#f5a623",
        "accessory": "parcel",
    },
    {
        "id": "analyst",
        "agentCode": "C",
        "code": "C",
        "name": "Analyst C",
        "role": "Rule mining analyst",
        "status": "done",
        "description": "Combines finance manual controls with network CIDDS learned rules.",
        "color": "#22a65a",
        "accessory": "chart",
    },
    {
        "id": "validator",
        "agentCode": "D",
        "code": "D",
        "name": "Validator D",
        "role": "Rule explanation and validation",
        "status": "done",
        "description": "Turns rules into cards and flags violations or suspicious coincidences.",
        "color": "#8b5cf6",
        "accessory": "shield",
    },
    {
        "id": "plugin",
        "agentCode": "E",
        "code": "E",
        "name": "Plugin E",
        "role": "Artifact packager",
        "status": "done",
        "description": "Packages dual-track reports, rule cards, and validation summaries for review.",
        "color": "#0ea5b7",
        "accessory": "package",
    },
    {
        "id": "pm",
        "agentCode": "F",
        "code": "F",
        "name": "PM F",
        "role": "Constrained chat owner",
        "status": "ready",
        "description": "Answers product questions using the office rule context and report artifacts.",
        "color": "#e35b8f",
        "accessory": "chat",
    },
]

AGENT_BY_CODE = {agent["agentCode"]: agent["id"] for agent in AGENTS}


def _rule_item(card: RuleCard, rules_by_id: dict[str, Any]) -> dict[str, Any]:
    rule = rules_by_id.get(card.rule_id)
    confidence = getattr(rule, "confidence", None)
    support = getattr(rule, "support", None)
    return {
        "id": card.rule_id,
        "text": getattr(rule, "text", None) or card.formula_text,
        "title": card.title_zh,
        "description": card.explanation_zh,
        "type": getattr(rule, "kind", None) or "rule",
        "enabled": bool(getattr(rule, "enabled", True)),
        "source": getattr(rule, "source", None) or "learned",
        "confidence": confidence if confidence is not None else support,
        "support": support,
        "coincidence": card.is_coincidence,
        "citation": card.citation,
        "tags": list(card.tags),
    }


def _group(
    *,
    group_id: str,
    name: str,
    domain: str,
    owner: str,
    cards: list[RuleCard],
    ruleset: RuleSet,
    description: str,
) -> dict[str, Any]:
    rules_by_id = {rule.rule_id: rule for rule in ruleset.rules}
    items = [_rule_item(card, rules_by_id) for card in cards]
    return {
        "id": group_id,
        "name": name,
        "domain": domain,
        "owner": owner,
        "description": description,
        "discovered": domain == "network",
        "from": "backend",
        "rules": items,
        "ruleCount": len(items),
        "enabledCount": sum(1 for item in items if item["enabled"]),
    }


def _summary(markdown: str, *, max_chars: int = 420) -> str:
    text = " ".join((markdown or "").replace("#", " ").split())
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _artifact(
    artifact_id: str,
    title: str,
    producer: str,
    kind: str,
    markdown: str,
    summary: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": artifact_id,
        "title": title,
        "producer": producer,
        "kind": kind,
        "time": "backend",
        "summary": summary,
        "preview": _summary(markdown),
        "markdown": markdown,
        "meta": meta or {},
    }


def build_office_state(
    *,
    finance: dict[str, Any],
    network: dict[str, Any],
    combined_ruleset: RuleSet,
    combined_cards: list[RuleCard],
    events: list[WorkflowEvent],
    request_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the UI-facing office state from real finance/network outputs."""
    finance_ruleset: RuleSet = finance["ruleset"]
    network_ruleset: RuleSet = network["ruleset"]
    finance_cards: list[RuleCard] = finance["cards"]
    network_cards: list[RuleCard] = network["cards"]
    finance_dual = finance["dual"]
    network_dual = network["dual"]
    finance_vreport = finance.get("vreport")

    rule_groups = [
        _group(
            group_id="office-finance-controls",
            name="Finance controls",
            domain="finance",
            owner="validator",
            cards=finance_cards,
            ruleset=finance_ruleset,
            description="Finance invariants, cross-period checks, and soft risk controls from finance_v1.",
        ),
        _group(
            group_id="office-network-controls",
            name="Network CIDDS controls",
            domain="network",
            owner="analyst",
            cards=network_cards,
            ruleset=network_ruleset,
            description="CIDDS NetFlow rules learned or loaded from archived network_cidds outputs.",
        ),
        {
            "id": "office-output-constraints",
            "name": "Output constraints",
            "domain": "chat",
            "owner": "pm",
            "description": "PM chat must cite rule groups and avoid unverified numbers.",
            "discovered": False,
            "from": "backend",
            "rules": [
                {
                    "id": "CHAT-01",
                    "text": "Answers must cite the active finance or network rule group when making a compliance claim.",
                    "title": "Cite active controls",
                    "description": "The PM agent can answer questions, but compliance claims must be grounded in backend rule cards.",
                    "type": "citation",
                    "enabled": True,
                    "source": "manual",
                    "confidence": 1.0,
                    "support": 1.0,
                    "coincidence": False,
                    "citation": "office_demo#chat",
                    "tags": ["chat", "constraint"],
                },
                {
                    "id": "CHAT-02",
                    "text": "Numerical claims must come from the latest constrained report slots or be marked as unverified.",
                    "title": "No unverified numbers",
                    "description": "This mirrors the existing /api/chat/constrained numeric whitelist behavior.",
                    "type": "numeric-guardrail",
                    "enabled": True,
                    "source": "manual",
                    "confidence": 1.0,
                    "support": 1.0,
                    "coincidence": False,
                    "citation": "office_demo#chat",
                    "tags": ["chat", "numeric"],
                },
            ],
            "ruleCount": 2,
            "enabledCount": 2,
        },
    ]

    data_sources = [
        {
            "id": "office-finance-source",
            "name": "Huaxin audit package",
            "kind": "csv",
            "scenario": "finance_v1",
            "status": "validated",
            "source": "finance_v1 synthetic package",
            "meta": {
                "rows": getattr(finance_vreport, "total_rows", None),
                "violations": len(getattr(finance_vreport, "violations", [])),
                "satisfactionRate": getattr(finance_vreport, "satisfaction_rate", None),
            },
        },
        {
            "id": "office-network-source",
            "name": "CIDDS NetFlow training sample",
            "kind": "csv",
            "scenario": "network_cidds",
            "status": "rules-loaded",
            "source": "network_cidds golden archive or NetNomos learner",
            "meta": {
                "ruleCount": len(network_ruleset.rules),
                "displayedCards": len(network_cards),
            },
        },
    ]

    artifacts = [
        _artifact(
            "office-finance-dual-report",
            "Finance dual-track report",
            "plugin",
            "report",
            finance_dual.track_b.markdown,
            "Constrained finance report with corrected slots and validation evidence.",
            {"scenario": "finance_v1", "violations": len(finance_dual.track_a.violations)},
        ),
        _artifact(
            "office-network-dual-report",
            "Network dual-track report",
            "plugin",
            "report",
            network_dual.track_b.markdown,
            "Constrained NetFlow generation summary with protocol and physical-bound checks.",
            {"scenario": "network_cidds", "violations": len(network_dual.track_a.violations)},
        ),
        _artifact(
            "office-rule-card-pack",
            "Combined office rule cards",
            "validator",
            "rules",
            "\n".join(f"- {card.rule_id}: {card.title_zh}" for card in combined_cards),
            "Finance and network rule cards packaged for the office wall.",
            {"scenario": "office_demo", "ruleCount": len(combined_ruleset.rules)},
        ),
    ]

    workflow_events = [
        {
            **asdict(event),
            "agentId": AGENT_BY_CODE.get(event.agent, "supervisor"),
        }
        for event in events
    ]

    return {
        "scenario": "office_demo",
        "agents": [dict(agent) for agent in AGENTS],
        "ruleGroups": rule_groups,
        "dataSources": data_sources,
        "artifacts": artifacts,
        "workflowEvents": workflow_events,
        "office": {
            "title": "NetNomos office demo",
            "summary": "Six office agents coordinate finance_v1 and network_cidds controls through the real backend job state.",
            "combinedRuleCount": len(combined_ruleset.rules),
            "combinedCardCount": len(combined_cards),
            "request": dict(request_params or {}),
        },
    }


def summarize_office_chat(message: str, state: dict[str, Any] | None) -> dict[str, Any]:
    """Deterministic constrained chat response for the office scenario."""
    if not state:
        return {
            "content": "Office demo state is not loaded yet. Start /api/rulesets/learn with scenario=office_demo first.",
            "matchedRules": [],
            "citations": [],
        }
    groups = state.get("ruleGroups", [])
    artifacts = state.get("artifacts", [])
    matched = []
    citations = []
    for group in groups[:3]:
        rules = group.get("rules") or []
        if rules:
            matched.append(rules[0]["text"])
            citations.append(f"{group['id']}#{rules[0]['id']}")
    content = (
        "Office demo is using backend state from finance_v1 and network_cidds. "
        f"Active groups: {', '.join(group['name'] for group in groups)}. "
        f"Artifacts available: {', '.join(item['title'] for item in artifacts)}. "
        "Use the finance group for audit-number claims, the network group for NetFlow claims, "
        "and the output constraints for PM chat responses."
    )
    if message:
        content += f" Request noted: {message}"
    return {"content": content, "matchedRules": matched, "citations": citations}
