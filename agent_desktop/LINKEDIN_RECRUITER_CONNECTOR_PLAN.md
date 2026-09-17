# LinkedIn Recruiter Connector Plan

This is the next track after the Dripify upload queue.

## Goal

Pull saved candidates from a LinkedIn Recruiter project without relying on Apify-style public scrapers.

## Shape

Keep this as a separate connector feeding the existing queue:

```text
LinkedIn Recruiter connector
  -> saved candidates JSON/CSV
  -> enrichment workflow
  -> POST /agent-ops/webhooks/processed-csv
  -> Dripify desktop upload agent
```

## Recommended Reverse-Engineering Method

1. Use the client's real logged-in browser session on client infrastructure.
2. Open Chrome DevTools Network tab on the Recruiter project saved-candidates page.
3. Filter for `voyager`, `recruiter`, `graphql`, and `project`.
4. Trigger the normal saved-candidate list view and export/list pagination.
5. Capture:
   - request URL
   - method
   - headers needed for CSRF/session
   - query/body params
   - pagination shape
   - response shape
6. Build a small connector adapter that accepts a captured endpoint profile and emits normalized candidates.

## Guardrails

- Run on client infra/IP/session.
- Keep request rate close to human browsing/export behavior.
- Never use LinkedIn credentials directly; reuse a browser session or client-provided cookies where legally approved.
- Store no raw cookies in logs.
- Stop on login, challenge, CAPTCHA, 2FA, or account warning.
- Make endpoint profiles configurable because LinkedIn can change internal routes.

## Output Contract

The connector should normalize to:

```json
{
  "linkedin_url": "https://www.linkedin.com/in/example",
  "full_name": "Jane Doe",
  "first_name": "Jane",
  "last_name": "Doe",
  "headline": "VP Engineering",
  "company": "Example Inc",
  "location": "New York, NY",
  "recruiter_project_id": "project-id",
  "recruiter_project_name": "Saved Candidates"
}
```

The enrichment workflow can then add email fields and post the final CSV into the Agent Ops webhook.
