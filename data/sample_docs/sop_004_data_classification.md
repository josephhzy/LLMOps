---
title: "Standard Operating Procedure: Data Classification and Handling"
doc_id: sop-004
classification: internal
version: "2.1"
last_updated: "2025-12-05"
---

# SOP-004: Data Classification and Handling

## 1. Purpose

This procedure establishes the framework for classifying, labelling, and handling data across all organisational systems. Proper data classification ensures that information receives an appropriate level of protection based on its sensitivity, legal requirements, and operational impact if disclosed.

## 2. Scope

This SOP applies to all data created, received, processed, or stored by the organisation, regardless of format (digital, paper, verbal). All personnel -- including staff, contractors, and third-party representatives -- are responsible for classifying data they originate and handling all data according to its assigned classification.

## 3. Classification Tiers

### 3.1 Public

Information approved for unrestricted distribution. Examples: published research papers, media releases, public-facing website content. No special handling controls are required, but release must be approved by the Communications Division.

### 3.2 Internal

Information intended for use within the organisation that does not contain sensitive personal data or operational intelligence. Examples: internal meeting minutes, project plans, training materials, non-sensitive correspondence. Disclosure outside the organisation could cause minor reputational impact.

### 3.3 Confidential

Information whose unauthorised disclosure could cause significant harm to operations, investigations, or individuals. Examples: vulnerability assessments, system architecture diagrams, partner coordination plans, personnel performance records. Access is restricted to individuals with a demonstrated need-to-know.

### 3.4 Restricted

The highest sensitivity tier. Information whose disclosure could cause severe damage to the organisation, endanger individuals, or compromise active investigations. Examples: threat intelligence reports, pseudonymised investigator identities, cryptographic key material, active case evidence. Access requires explicit authorisation from the Data Owner and ISO clearance.

## 4. Handling Requirements by Tier

| Requirement | Public | Internal | Confidential | Restricted |
|------------|--------|----------|--------------|------------|
| Encryption at rest | Optional | Recommended | Required (AES-256) | Required (AES-256, HSM-managed keys) |
| Encryption in transit | TLS 1.2+ | TLS 1.2+ | TLS 1.3 required | TLS 1.3 + VPN or dedicated link |
| Access control | None | RBAC | RBAC + need-to-know | RBAC + individual approval + MFA |
| Storage location | Any approved system | Organisation-managed systems | Compliance-certified cloud or on-premises | Air-gapped or SEV-approved enclaves |
| Sharing externally | Permitted | With NDA | CISO approval required | Data Governance Committee approval |
| Retention | Per business need | 3 years minimum | 5 years minimum | 7 years minimum or as directed |

## 5. Labelling Standards

All documents must carry a classification label in the header or footer of every page. Digital files must include the classification in the filename suffix (e.g., `report_2025Q3_CONFIDENTIAL.pdf`) and in the document metadata properties. Emails containing Confidential or Restricted information must include the classification in the subject line prefix, such as `[CONFIDENTIAL]`.

Unlabelled data discovered during audits shall be treated as Confidential until the Data Owner assigns a classification. The Data Owner must respond to classification requests within 5 business days.

## 6. Declassification

Data may be declassified when the conditions requiring its original classification no longer apply. Declassification requests must be submitted to the Data Owner with a written justification. The ISO reviews all declassification requests for Confidential and Restricted data. Approved declassifications are logged in the Data Classification Register and labels must be updated within 10 business days. Bulk declassification (more than 50 records) requires Division Director approval.
