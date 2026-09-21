# Clean Air & Climate Resilience — Security & Trust

## 1. Security Goal

The platform handles:

- citizen-submitted photographs
- location information
- operational incidents
- environmental observations
- model outputs

The design must minimize unnecessary data collection and prevent one user's input from becoming an uncontrolled administrative action.

---

## 2. Trust Boundaries

```text
Citizen
   ↓
Public API
   ↓
Validation
   ↓
Backend
   ↓
AI / Data services
   ↓
Operational database
   ↓
Authority interface
```

The frontend is never trusted for authorization decisions.

---

## 3. Citizen Data

Collect only what is needed for the pollution report:

- image
- approximate/necessary location
- timestamp
- optional description
- report identifier

Avoid collecting unrelated personal information.

---

## 4. Image Handling

Citizen images should:

- be checked for allowed file type
- have a size limit
- be scanned/validated before processing
- be stored with controlled access
- be given a retention policy
- not be publicly exposed by default

Do not place raw image URLs directly into public event pages.

---

## 5. Location Privacy

Citizen location can be sensitive.

Recommended approach:

```text
Exact location
    ↓
restricted internal record

Public/aggregate visualization
    ↓
coarsened location
```

The prototype should avoid displaying an individual reporter's precise coordinates to other public users unless there is a justified operational reason.

---

## 6. Authentication

The authority console must require authentication.

Recommended roles:

```text
ADMIN
AUTHORITY
FIELD_OPERATOR
ANALYST
CITIZEN
```

Role permissions must be checked server-side.

---

## 7. Authorization

Example:

### Citizen

Can:

- submit report
- view own report status

Cannot:

- create official alert
- change event severity
- mark incident resolved

### Field operator

Can:

- view assigned incidents
- update investigation status
- add verification evidence

### Authority

Can:

- review events
- create alerts
- assign field teams
- resolve incidents

### Admin

Can:

- manage users
- configure nodes
- manage system settings

---

## 8. AI Security

All Gemini responses must be treated as untrusted model output.

Pipeline:

```text
Gemini
  ↓
schema validation
  ↓
semantic validation
  ↓
policy checks
  ↓
backend decision
```

Never directly execute model-generated code, SQL, shell commands, or arbitrary API calls.

---

## 9. Prompt Injection

Citizen-submitted images/descriptions may contain adversarial text.

Rules:

- treat user content as data
- keep system instructions separate
- validate structured output
- do not let image text override system rules
- never expose secrets to the model
- do not place API keys in prompts

---

## 10. Secrets

Never commit:

- API keys
- service-account private keys
- Firebase admin credentials
- database credentials
- Earth Engine credentials

Use environment variables or the cloud provider's secret-management system.

Commit only:

```text
.env.example
```

with fake/example variable names.

---

## 11. External Data

External data should be treated as untrusted input.

Validate:

- types
- timestamps
- coordinate ranges
- numeric ranges
- duplicates
- source identifiers

Keep source metadata and timestamps so every event can be traced back to its inputs.

---

## 12. Audit Logging

Record:

```text
who
did what
when
to which event
based on which state
```

Examples:

```text
EVENT_CREATED
ALERT_CREATED
ASSIGNMENT_CHANGED
STATUS_CHANGED
REPORT_REVIEWED
MODEL_UPDATED
FEDERATION_ROUND_COMPLETED
```

Do not allow ordinary users to edit audit records.

---

## 13. Model Safety

The system must not automatically:

- accuse a named company
- accuse a named person
- issue legal enforcement
- declare an illegal act
- publish unsupported causal claims

Recommended phrasing:

> "Possible combustion-related event; human verification required."

---

## 14. Data Integrity

Every event should retain:

- source timestamps
- source identifiers
- model version
- prompt/schema version for AI-generated fields
- event-engine version
- evidence used at creation time

This makes results reproducible and auditable.

---

## 15. Availability

External APIs may fail.

Fallback behavior:

```text
source fails
   ↓
mark unavailable
   ↓
continue with available evidence
   ↓
adjust evidence coverage
```

Never fabricate replacement values.

Replay mode provides demo availability.

---

## 16. Rate Limiting

Protect:

- citizen upload endpoint
- Gemini analysis endpoint
- event detection endpoint
- federation endpoints

Use rate limits and payload limits.

---

## 17. Database Security

Firestore:

- deny client-side access to sensitive authority collections unless explicitly required
- enforce security rules
- prefer server-side writes for sensitive state transitions

BigQuery:

- separate data ingestion, model access and analyst permissions
- keep service-account permissions minimal

---

## 18. Principle of Least Privilege

Every service account should receive only the permissions it needs.

Examples:

```text
Frontend
→ no database-admin credentials

Gemini service
→ no direct database-admin permission

Ingestion worker
→ write required analytical tables only

Authority API
→ operational database access needed for workflow only
```

---

## 19. Security Definition of Done

Before demo:

- no secrets in Git
- authentication works
- role checks work
- upload validation works
- oversized files are rejected
- AI output is schema-validated
- sensitive collections are protected
- audit logging works
- replay data is clearly labeled
- failure paths do not invent data
