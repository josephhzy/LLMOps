---
title: "Standard Operating Procedure: Access Control and Identity Management"
doc_id: sop-003
classification: internal
version: "4.0"
last_updated: "2026-01-10"
---

# SOP-003: Access Control and Identity Management

## 1. Purpose

This procedure governs the provisioning, modification, and revocation of access to organisation information systems. It ensures that only authorised personnel have access to resources necessary for their role, in accordance with the principle of least privilege and the organisation's internal IT governance standards (aligned with ISO 27001 and NIST 800-53).

## 2. Scope

This SOP covers all organisation-managed systems, including on-premises infrastructure, public and private cloud tenancies, SaaS applications, and third-party integration points. It applies to all staff, contractors, interns, and service accounts.

## 3. Role-Based Access Control (RBAC)

Access rights are assigned based on predefined roles rather than individual requests. The following standard roles are maintained:

| Role | Access Level | Example Permissions |
|------|-------------|-------------------|
| **Viewer** | Read-only access to non-sensitive data | Dashboard viewing, report downloads |
| **Analyst** | Read and limited write access | Case data entry, query execution, tool usage |
| **Senior Analyst** | Extended write and approval rights | Evidence submission, workflow approval |
| **Team Lead** | Full division-level access | User management within team, audit log review |
| **Administrator** | System-level configuration | Infrastructure changes, security policy updates |

Custom roles must be approved by the Information Security Office (ISO) and documented in the Access Control Register before implementation.

## 4. Principle of Least Privilege

All access grants must satisfy the minimum permissions required for the individual's current duties. Broad or standing privileges (e.g., domain admin) are prohibited for day-to-day operations. Privileged access must be requested through the Privileged Access Management (PAM) system on a just-in-time basis, with a maximum session duration of 4 hours.

## 5. Access Request and Approval Workflow

1. **Request** -- The user submits an access request via the IT Service Portal, specifying the system, role, and business justification.
2. **Line Manager Approval** -- The requestor's reporting officer reviews and endorses the request within 2 business days.
3. **Data Owner Approval** -- The designated data owner for the target system approves the access level.
4. **ISO Review** -- For Confidential or Restricted systems, the ISO conducts a risk assessment before granting access.
5. **Provisioning** -- The IT Operations team provisions access within 1 business day of final approval.
6. **Confirmation** -- The requestor receives a notification and must verify access within 3 business days. Unverified accounts are automatically suspended.

## 6. Quarterly Access Reviews

All system access is reviewed every quarter. Division Heads must certify that each individual's access remains appropriate for their current role. Accounts with no login activity for 60 consecutive days are flagged for deactivation. Orphaned accounts (belonging to departed staff) discovered during review must be disabled within 24 hours and reported as a security event.

## 7. Multi-Factor Authentication (MFA)

MFA is mandatory for all organisation systems. The approved MFA methods are:

- **Primary**: Hardware security key (FIDO2-compliant, e.g., YubiKey 5 series)
- **Secondary**: Time-based one-time password (TOTP) via the approved authenticator application
- **Emergency**: One-time bypass codes issued by the IT Helpdesk, valid for 24 hours, limited to 3 per quarter

SMS-based OTP is explicitly prohibited due to SIM-swap vulnerabilities. Biometric authentication (fingerprint, facial recognition) may be used as an additional factor but cannot serve as the sole second factor. All MFA enrolment changes require in-person identity verification at the IT Helpdesk.
