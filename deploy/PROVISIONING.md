# Ironpass — Tenant Provisioning Guide
# Three curl commands to onboard a customer.

BASE_URL=https://ironpass-production.up.railway.app
ADMIN_SECRET=your_ironpass_admin_secret_here

# ─────────────────────────────────────
# Step 1: Create the tenant
# ─────────────────────────────────────
curl -s -X POST "$BASE_URL/v1/admin/tenants" \
  -H "Authorization: Bearer $ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "active_rulesets": ["pci_dss", "hipaa"]
  }' | jq .

# Response:
# {
#   "id": "3f2c1a4b-...",
#   "name": "Acme Corp",
#   "active_rulesets": ["pci_dss", "hipaa"],
#   "is_active": true,
#   "created_at": "2026-03-31T..."
# }
# → Copy the "id" value for Step 2.

# ─────────────────────────────────────
# Step 2: Issue an API key
#   Replace TENANT_ID with the id from Step 1
# ─────────────────────────────────────
TENANT_ID=3f2c1a4b-xxxx-xxxx-xxxx-xxxxxxxxxxxx

curl -s -X POST "$BASE_URL/v1/admin/tenants/$TENANT_ID/keys" \
  -H "Authorization: Bearer $ADMIN_SECRET" | jq .

# Response:
# {
#   "key_id": "8a7b6c5d-...",
#   "raw_key": "dbnc_live_a4f2b891...",   ← COPY THIS
#   "key_prefix": "dbnc_live_a4f2b8",
#   "tenant_id": "3f2c1a4b-...",
#   "message": "Store this key securely. It will not be shown again."
# }
# → Send the raw_key to the customer. It will not be shown again.

# ─────────────────────────────────────
# Step 3: Send the customer their one-line integration
# ─────────────────────────────────────
# Tell them to replace two things in their code:
#
#   base_url  = "https://ironpass-production.up.railway.app/openai/v1"
#   api_key   = "dbnc_live_a4f2b891..."     ← their Ironpass key
#
# Their OpenAI calls stay exactly the same. Only the URL and key change.
# They still pass their real OpenAI key in: X-OpenAI-Key: sk-...

# ─────────────────────────────────────
# Key rotation (when needed)
# ─────────────────────────────────────
# Issue a new key (Step 2 again), customer switches to it, then revoke old:

KEY_ID=8a7b6c5d-xxxx-xxxx-xxxx-xxxxxxxxxxxx

curl -s -X POST "$BASE_URL/v1/admin/tenants/$TENANT_ID/keys/$KEY_ID/revoke" \
  -H "Authorization: Bearer $ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"reason": "scheduled_rotation"}' | jq .

# ─────────────────────────────────────
# Offboarding a tenant
# ─────────────────────────────────────
curl -s -X DELETE "$BASE_URL/v1/admin/tenants/$TENANT_ID" \
  -H "Authorization: Bearer $ADMIN_SECRET" | jq .

# Cascade: revokes all keys → invalidates vault tokens → marks tenant inactive
# GDPR Article 17 compliant.

# ─────────────────────────────────────
# Available rulesets
# ─────────────────────────────────────
# pci_dss   — Payment Card Industry (credit cards, CVVs, card expiry)
# hipaa     — Healthcare (names, dates of birth, diagnosis codes, NPI numbers)
# gdpr      — EU data protection (emails, IPs, any personal identifiers)
# soc2      — Security controls (API keys, passwords, tokens)
#
# Combine freely: ["pci_dss", "hipaa"] applies both frameworks simultaneously.
# Conflicts resolved by severity: Block > Tokenize > Pseudonymize > Mask
