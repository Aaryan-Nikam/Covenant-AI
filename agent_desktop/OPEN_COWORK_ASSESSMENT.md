# Open Cowork Assessment

Repo reviewed: `https://github.com/coasty-ai/open-cowork`

## Verdict

Open Cowork is directly relevant and stronger than using `open-computer-use` MCP alone. It already packages the product pattern we need:

- shared screenshot -> predict -> execute loop
- executor abstraction for local desktop, remote machine, and browser
- local desktop executor with coordinate scaling
- BYO vision provider support
- approval/cancel/run timeline concepts
- backend key custody so client apps do not hold API keys
- mock Coasty server for deterministic tests

## What To Reuse

1. **Executor shape**

   Their `Executor` interface is the right narrow waist:

   ```text
   screenshot() -> image + dimensions
   execute(action)
   dimensions()
   dispose()
   ```

2. **Coordinate scaling**

   The model clicks in screenshot coordinates. The OS clicks in real screen coordinates. Those can differ because of DPI scaling, monitor selection, or capture region. We ported this idea into our local adapter.

3. **No raw code actions**

   Open Cowork refuses model-generated raw code on every executor. Our action schema does not expose raw execution at all, which is the right default.

4. **Run supervision**

   Their event timeline and cancel flow are product-grade. For our first client build, we can start with local JSONL ledgers, then add a UI/timeline later if needed.

5. **BYO model provider**

   Their `@open-cowork/llm` package has a mature OpenAI-compatible provider with structured JSON output and text repair. We should either reuse that package in a TypeScript runner or copy the design into our Python `JsonVisionBrain`.

## What Not To Reuse Blindly

- Their generic `runAgentLoop` executes predicted actions directly. For our Dripify workflow, we keep our explicit policy gate before every action.
- Their macOS bridge depends on `cliclick`. That is okay for client installs, but it must be part of onboarding.
- Their local run has no mouse-corner panic button. Our Python `pyautogui` adapter keeps `FAILSAFE` enabled.
- Their desktop app is broader than our need. We do not need web/mobile/backend surfaces for a one-client Dripify agent yet.

## Product Direction

Keep our current policy-gated agent package as the workflow safety layer.

Use Open Cowork as the reference implementation for:

- local native executor hardening
- model provider output repair
- desktop UI/cancel/timeline if this becomes multi-client

For the next implementation step, wire a real vision model client into `JsonVisionBrain`, then test on a local fake Dripify page before touching the real Dripify account.
