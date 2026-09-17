# Azmeth Desktop Agent

Local, client-owned desktop agent for browser workflows that should run through a real logged-in user browser instead of brittle DOM automation.

The first production workflow is Dripify CSV upload. The agent is intentionally conservative:

- runs on the client's machine and browser profile
- uses screenshot, mouse, keyboard, wait, and file chooser actions as the core control surface
- stores per-run screenshots and append-only JSONL logs
- only runs allowlisted workflows and URLs
- stops for login, 2FA, CAPTCHA, payment, permission, or destructive screens
- may complete configured CSV imports without human confirmation
- blocks campaign settings, sequence edits, limit changes, billing, integrations, and destructive actions

## Layout

```text
agent_desktop/
  azmeth_agent/
    agent_loop.py       # model/tool execution loop
    actions.py          # allowed desktop action schema
    config.py           # client/workflow config
    llm.py              # model adapter protocol
    logging.py          # append-only run ledger
    policy.py           # safety rules and stop conditions
    tools.py            # browser/desktop tool protocol
    workflows.py        # Dripify workflow factory
  config/
    client.example.yaml
```

## Why This Shape

The workflow code should know the business goal, but not know how the browser is controlled. That lets us swap the implementation underneath:

- Open Computer Use / Coasty MCP for desktop control
- Browser Harness for persistent real-browser control
- a custom local adapter using OS screenshots and mouse/keyboard
- test doubles for deterministic CI

## Next Wiring Step

Implement one concrete `DesktopTools` adapter for the client machine. The recommended first adapter is an MCP bridge to Open Computer Use / Coasty, because it already exposes the right category of desktop/browser tools.

## Run

From this directory:

```bash
PYTHONPATH=. python -m azmeth_agent.runner \
  --config config/client.example.yaml \
  --csv /absolute/path/to/dripify_leads.csv \
  --mode dry-run \
  --runtime-dir /tmp/azmeth-agent
```

Run from a queued webhook job:

```bash
PYTHONPATH=. python -m azmeth_agent.runner \
  --config config/client.example.yaml \
  --job-id <upload-job-id> \
  --job-queue-dir /tmp/azmeth-agent/upload-jobs \
  --mode local
```

Coasty MCP mode:

```bash
COASTY_API_KEY=sk-coasty-... \
COASTY_MACHINE_ID=mch_... \
PYTHONPATH=. python -m azmeth_agent.runner \
  --config config/client.example.yaml \
  --csv /absolute/path/to/dripify_leads.csv \
  --campaign "Campaign name" \
  --mode coasty
```

`coasty` mode currently wires the MCP transport and tool adapter. The vision model client is intentionally left as a guarded stub until the approved model provider and key handling are configured.

Vision model configuration for `local` or `coasty` mode:

```bash
VISION_MODEL_BASE_URL=https://api.openai.com/v1 \
VISION_MODEL_API_KEY=sk-... \
VISION_MODEL_NAME=gpt-4.1 \
PYTHONPATH=. python -m azmeth_agent.runner \
  --config config/client.example.yaml \
  --csv /absolute/path/to/dripify_leads.csv \
  --campaign "Campaign name" \
  --mode local
```

If those three model values are absent, real modes use a guarded stub that escalates immediately.
