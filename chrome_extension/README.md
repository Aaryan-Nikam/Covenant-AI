# Azmeth Dripify Agent Extension

Chrome MV3 extension for the Dripify upload agent.

This is the product UI/control surface for the local agent. It is separate from the existing Covenant/Ironpass dashboard.

## What It Does

- Shows processed CSV upload jobs received by the local Agent Ops webhook.
- Opens a selected Dripify campaign/job context in the active browser.
- Provides OpenClaw-style browser control tools through Chrome Debugger Protocol:
  - screenshot
  - click
  - type text
  - scroll
  - navigate
- Avoids normal DOM automation as the primary control layer.

## Important Browser Limits

A Chrome extension can control tabs through Chrome Debugger Protocol, but it cannot reliably operate native OS file chooser dialogs. For CSV upload, the extension should coordinate with the local desktop/native agent for the actual file selection step, or use an explicitly approved file-input bridge later.

## Local Test Setup

1. Start the Agent Ops API:

```bash
PYTHONPATH=. AGENT_OPS_QUEUE_DIR=/tmp/azmeth-agent/upload-jobs \
  uvicorn engine.agent_ops.dev_server:app --host 127.0.0.1 --port 8010
```

2. Load extension:

```text
chrome://extensions
Developer mode -> Load unpacked -> /Users/aaryannikam/debounce/chrome_extension
```

3. Open the side panel from the extension icon.

## Default Local API

```text
http://127.0.0.1:8010
```
