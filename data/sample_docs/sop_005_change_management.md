---
title: "Standard Operating Procedure: Change Management"
doc_id: sop-005
classification: internal
version: "3.0"
last_updated: "2026-02-18"
---

# SOP-005: Change Management

## 1. Purpose

This procedure governs the process for requesting, evaluating, approving, implementing, and reviewing changes to production systems and infrastructure. It ensures that changes are introduced in a controlled manner, minimising disruption to business-critical operations and maintaining system integrity.

## 2. Scope

This SOP applies to all changes affecting production environments, including but not limited to: software deployments, infrastructure modifications, database schema changes, network configuration updates, security policy changes, and third-party integration updates. Development and sandbox environments are excluded unless they share resources with production.

## 3. Change Request Process

### 3.1 Submission

The Change Requestor submits a Change Request (CR) via the IT Service Management (ITSM) portal. Each CR must include:

- **Description** of the proposed change and its business justification
- **Impact assessment** identifying affected systems, users, and dependencies
- **Risk rating** (Low, Medium, High, Critical) based on the Change Risk Matrix
- **Implementation plan** with step-by-step instructions and assigned personnel
- **Rollback plan** detailing how to revert if the change fails
- **Testing evidence** confirming the change was validated in a non-production environment
- **Proposed implementation window** (must fall within an approved maintenance window for Medium+ risk changes)

### 3.2 Change Advisory Board (CAB) Review

The CAB convenes weekly on Tuesdays at 14:00 UTC to review pending CRs. Membership includes representatives from Infrastructure, Application Development, Security, and Operations. The CAB evaluates each CR against the following criteria:

- Technical soundness and completeness of documentation
- Potential impact on service availability and SLA commitments
- Adequacy of rollback and contingency plans
- Resource availability during the proposed window
- Conflicts with other scheduled changes

The CAB may approve, reject, or defer a CR. Rejected CRs must include a written rationale. Deferred CRs are re-evaluated at the next session.

## 4. Rollback Planning

Every CR rated Medium or above must include a tested rollback plan. The rollback plan must specify the maximum allowable implementation time before an automatic rollback is triggered. For database changes, a verified backup must be completed no more than 2 hours before the change window opens. Rollback drills for Critical changes must be conducted in the staging environment prior to CAB review.

## 5. Testing Requirements

All changes must pass the following gates before production deployment:

1. **Unit testing** -- Developer-verified functional correctness
2. **Integration testing** -- Validated in the staging environment against dependent systems
3. **Security scan** -- Automated SAST/DAST scan with no Critical or High findings unresolved
4. **Performance testing** -- Required for changes expected to affect throughput or latency by more than 10%
5. **User acceptance testing (UAT)** -- Required for changes affecting end-user workflows; sign-off from the Business Owner

## 6. Emergency Change Procedures

Emergency changes are permitted only when an unplanned outage or critical vulnerability requires immediate remediation. The process is as follows:

1. The on-call engineer implements the fix with verbal approval from the Duty Manager.
2. A retrospective CR must be submitted within 24 hours documenting the change, justification, and outcome.
3. The CAB reviews all emergency changes at the next scheduled meeting.
4. More than 3 emergency changes in a calendar month triggers a process review by the Service Management Office.

Emergency changes that fail must be escalated to the CISO and Division Director within 30 minutes.

## 7. Post-Implementation Review

All High and Critical changes require a Post-Implementation Review (PIR) within 5 business days of deployment. The PIR assesses whether the change achieved its intended outcome, identifies any unintended side effects, and captures lessons learned for future changes.
