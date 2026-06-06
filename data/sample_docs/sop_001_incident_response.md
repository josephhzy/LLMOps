---
title: "Standard Operating Procedure: Cybersecurity Incident Response"
doc_id: sop-001
classification: internal
version: "3.2"
last_updated: "2025-11-15"
---

# SOP-001: Cybersecurity Incident Response

## 1. Purpose

This procedure establishes a structured framework for detecting, triaging, containing, and resolving cybersecurity incidents affecting organisation systems and infrastructure. It ensures consistent response across all divisions and minimises impact to business-critical operations.

## 2. Scope

This SOP applies to all personnel operating within the Technology Divisions, including full-time staff, contractors, and vendor representatives who have access to organisation-managed networks or systems.

## 3. Severity Classification

All incidents must be classified within 15 minutes of initial detection:

| Severity | Description | Example | Response Target |
|----------|-------------|---------|-----------------|
| **P1 - Critical** | Active compromise of business-critical systems or exfiltration of restricted data | Ransomware on production monitoring network | Immediate (within 15 min) |
| **P2 - High** | Significant degradation of operational capability or confirmed intrusion attempt | Brute-force attack on analyst portal | Within 1 hour |
| **P3 - Medium** | Contained security event with limited operational impact | Malware detected and quarantined on standalone workstation | Within 4 hours |
| **P4 - Low** | Minor policy violation or anomaly requiring investigation | Repeated failed login from known IP range | Within 24 hours |

## 4. Triage Steps

1. **Detection & Logging** -- Record the alert source, timestamp (UTC), affected asset(s), and initial indicators of compromise (IOCs) in the Incident Management System (IMS).
2. **Initial Assessment** -- The on-call Security Analyst assigns a preliminary severity level using the matrix above.
3. **Containment Decision** -- For P1/P2, the analyst must isolate affected segments immediately and notify the Incident Commander (IC). For P3/P4, standard containment checklists apply.
4. **Evidence Preservation** -- Before remediation, capture volatile memory, network logs, and disk images per SOP-002 (Evidence Handling).
5. **Eradication & Recovery** -- Remove threat artefacts, patch exploited vulnerabilities, and restore services from verified clean backups.

## 5. Escalation Matrix

| Severity | Notify Within | Notified Parties | Escalation Tier |
|----------|---------------|------------------|-----------------|
| P1 | 15 minutes | IC, CISO, Division Director, Legal Liaison | Tier 3 Escalation |
| P2 | 30 minutes | IC, CISO, Team Lead | Tier 2 Escalation |
| P3 | 2 hours | Team Lead, SOC Manager | Tier 1 Escalation |
| P4 | Next business day | SOC Manager | Tier 1 Escalation |

For P1 incidents, the CISO must brief the Executive Risk Committee within 2 hours. External notification to the contracted MSSP / SOC Provider is mandatory for P1 and recommended for P2.

## 6. Notification Timelines

- **Internal stakeholders**: As per the escalation matrix above.
- **Affected data subjects**: Within 72 hours if personal data is involved, per applicable data protection regulations (e.g., GDPR).
- **Regulatory bodies**: Within 48 hours for P1 incidents involving regulated or restricted data, in line with industry-standard breach-notification requirements.

## 7. Post-Incident Review

A Post-Incident Review (PIR) must be convened within 5 business days of incident closure. The PIR report shall include root cause analysis, timeline reconstruction, effectiveness of containment measures, and recommended improvements. All PIR findings are tracked in the IMS until remediation is verified complete.
