from __future__ import annotations

import argparse
import os
from dataclasses import replace
from pathlib import Path

from azmeth_agent.actions import AgentAction
from azmeth_agent.agent_loop import AgentLoop
from azmeth_agent.coasty_tools import CoastyDesktopTools
from azmeth_agent.config import AgentConfig
from azmeth_agent.job_queue import load_job_csv_path
from azmeth_agent.llm import ScriptedBrain
from azmeth_agent.local_desktop_tools import LocalDesktopTools
from azmeth_agent.logging import RunLedger
from azmeth_agent.mcp_client import McpServerCommand, StdioMcpClient
from azmeth_agent.model_clients import OpenAICompatibleConfig, OpenAICompatibleVisionClient
from azmeth_agent.policy import SafetyPolicy
from azmeth_agent.tools import DryRunTools
from azmeth_agent.vision_brain import JsonVisionBrain, VisionModelClient
from azmeth_agent.workflows import build_dripify_upload_task


class MissingModelClient(VisionModelClient):
    def decide(self, prompt: str, screenshot_path: Path) -> str:
        return (
            '{"action_type":"escalate","reason":"model client not configured",'
            '"message":"A real vision model client has not been wired yet."}'
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Azmeth desktop browser agent.")
    parser.add_argument("--config", type=Path, default=Path("config/client.example.yaml"))
    parser.add_argument("--workflow", default="dripify_csv_upload")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--job-queue-dir", type=Path, default=Path("/tmp/azmeth-agent/upload-jobs"))
    parser.add_argument("--campaign", default=None)
    parser.add_argument("--mode", choices=("dry-run", "local", "coasty"), default="dry-run")
    parser.add_argument("--runtime-dir", type=Path, default=None)
    parser.add_argument("--ledger-secret", default=os.getenv("AZMETH_AGENT_LEDGER_SECRET", "dev-ledger-secret"))
    parser.add_argument("--coasty-machine-id", default=os.getenv("COASTY_MACHINE_ID"))
    parser.add_argument("--coasty-api-key", default=os.getenv("COASTY_API_KEY"))
    parser.add_argument("--model-base-url", default=os.getenv("VISION_MODEL_BASE_URL"))
    parser.add_argument("--model-api-key", default=os.getenv("VISION_MODEL_API_KEY"))
    parser.add_argument("--model-name", default=os.getenv("VISION_MODEL_NAME"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = AgentConfig.from_yaml(args.config)
    if args.runtime_dir:
        runtime_dir = args.runtime_dir.expanduser()
        config = replace(
            config,
            chrome_profile_dir=runtime_dir / "chrome-profile",
            downloads_dir=runtime_dir / "downloads",
            evidence_dir=runtime_dir / "evidence",
            run_log_dir=runtime_dir / "logs",
        )
    workflow = config.workflow(args.workflow)
    csv_path = resolve_csv_path(args)
    task = build_dripify_upload_task(csv_path, campaign_hint=args.campaign)
    ledger = RunLedger(config.run_log_dir, secret=args.ledger_secret)
    policy = SafetyPolicy(workflow)

    mcp_client = None
    if args.mode == "dry-run":
        tools = DryRunTools(config.evidence_dir / ledger.run_id, current_url=workflow.start_url)
        brain = ScriptedBrain([AgentAction.complete("dry run", "Dry run completed.")])
    elif args.mode == "local":
        tools = LocalDesktopTools(config.evidence_dir / ledger.run_id)
        brain = JsonVisionBrain(build_model_client(args))
    else:
        if not args.coasty_machine_id:
            raise SystemExit("--coasty-machine-id or COASTY_MACHINE_ID is required for coasty mode.")
        env = dict(os.environ)
        if args.coasty_api_key:
            env["COASTY_API_KEY"] = args.coasty_api_key
        mcp_client = StdioMcpClient(
            McpServerCommand(command="npx", args=("-y", "@coasty/mcp"), env=env)
        )
        tools = CoastyDesktopTools(
            mcp_client,
            machine_id=args.coasty_machine_id,
            evidence_dir=config.evidence_dir / ledger.run_id,
        )
        brain = JsonVisionBrain(build_model_client(args))

    try:
        result = AgentLoop(workflow, policy, tools, brain, ledger).run(task)
        print(result)
        print(f"Run log: {ledger.path}")
    finally:
        if mcp_client:
            mcp_client.close()


def build_model_client(args: argparse.Namespace) -> VisionModelClient:
    if args.model_base_url and args.model_api_key and args.model_name:
        return OpenAICompatibleVisionClient(
            OpenAICompatibleConfig(
                base_url=args.model_base_url,
                api_key=args.model_api_key,
                model=args.model_name,
            )
        )
    return MissingModelClient()


def resolve_csv_path(args: argparse.Namespace) -> Path:
    if args.csv:
        return args.csv
    if args.job_id:
        return load_job_csv_path(args.job_queue_dir, args.job_id)
    raise SystemExit("Either --csv or --job-id is required.")


if __name__ == "__main__":
    main()
