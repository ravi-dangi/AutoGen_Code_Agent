"""CodePilot AI — AutoGen coding agent with Docker sandbox execution."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.code_execution import PythonCodeExecutionTool
from dotenv import load_dotenv

load_dotenv()

SYSTEM_MESSAGE = """You are CodePilot, an autonomous Python coding agent.

Workflow for every request:
1. Write clear, working Python code that solves the user's task.
2. Execute the code using the code_executor tool.
3. If execution fails, read the error, fix the code, and execute again.
4. Repeat until the code runs successfully or you have tried 3 fixes.
5. After success, briefly explain what the code does and summarize the output.

Rules:
- Always execute your code — do not only describe it.
- Prefer standard-library Python only (no pip installs).
- Print the final results so they appear in the execution output.
- Keep code simple and readable.
"""

WORK_DIR = Path(__file__).resolve().parent.parent / ".work"
WORK_DIR.mkdir(exist_ok=True)


@dataclass
class AgentResult:
    """Parsed outcome from one agent run."""

    generated_code: str = ""
    execution_output: str = ""
    final_response: str = ""
    success: bool = False
    attempts: list[dict[str, str]] = field(default_factory=list)
    raw_messages: list[Any] = field(default_factory=list)


def _extract_code_from_tool_args(arguments: str) -> str:
    """Pull Python source from a tool-call arguments JSON string."""
    try:
        data = json.loads(arguments)
        return str(data.get("code", "") or "")
    except Exception:
        match = re.search(r'"code"\s*:\s*"(.*)"', arguments, re.DOTALL)
        if not match:
            return arguments
        return bytes(match.group(1), "utf-8").decode("unicode_escape")


def _parse_result(messages: list[Any]) -> AgentResult:
    """Turn AutoGen messages into UI-friendly fields."""
    result = AgentResult(raw_messages=messages)
    last_code = ""
    last_output = ""

    for msg in messages:
        msg_type = type(msg).__name__

        # Tool call → generated code
        if msg_type == "ToolCallRequestEvent" and getattr(msg, "content", None):
            for call in msg.content:
                args = getattr(call, "arguments", "") or ""
                code = _extract_code_from_tool_args(args)
                if code:
                    last_code = code
                    result.attempts.append({"code": code, "output": ""})

        # Tool result → execution output
        elif msg_type == "ToolCallExecutionEvent" and getattr(msg, "content", None):
            for exec_result in msg.content:
                output = getattr(exec_result, "content", "") or ""
                last_output = output
                if result.attempts:
                    result.attempts[-1]["output"] = output
                is_error = bool(getattr(exec_result, "is_error", False))
                result.success = (not is_error) and ("Traceback" not in output)

        # Final natural-language reply
        elif isinstance(msg, TextMessage) and msg.source != "user":
            result.final_response = msg.content
        elif msg_type in ("ToolCallSummaryMessage", "TextMessage"):
            content = getattr(msg, "content", "") or ""
            source = getattr(msg, "source", "")
            if source != "user" and content:
                result.final_response = content

    result.generated_code = last_code
    result.execution_output = last_output

    # If agent never set a final text reply, synthesize one
    if not result.final_response:
        if result.success:
            result.final_response = "Code executed successfully.\n\n" + last_output
        else:
            result.final_response = "Execution finished with errors.\n\n" + last_output

    return result


async def run_coding_task(
    task: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> AgentResult:
    """
    Generate Python code, run it in a Docker sandbox, and auto-fix on errors.

    conversation_history: optional list of {"role": "user"|"assistant", "content": "..."}
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is missing. Set it in a .env file.")

    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    # Optional short memory for follow-up questions
    prompt = task
    if conversation_history:
        lines = []
        for turn in conversation_history[-6:]:  # last 3 exchanges
            role = turn.get("role", "user").capitalize()
            lines.append(f"{role}: {turn.get('content', '')}")
        prompt = (
            "Conversation so far:\n"
            + "\n".join(lines)
            + f"\n\nNew request: {task}"
        )

    # OpenRouter is OpenAI-compatible; model_info is required for non-OpenAI model ids
    model_client = OpenAIChatCompletionClient(
        model=model,
        api_key=api_key,
        base_url=base_url,
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "structured_output": True,
            "family": "unknown",
        },
    )

    async with DockerCommandLineCodeExecutor(
        work_dir=WORK_DIR,
        timeout=60,
        auto_remove=True,
        stop_container=True,
    ) as executor:
        code_tool = PythonCodeExecutionTool(executor)

        agent = AssistantAgent(
            name="code_pilot",
            model_client=model_client,
            tools=[code_tool],
            system_message=SYSTEM_MESSAGE,
            reflect_on_tool_use=True,
            max_tool_iterations=5,  # generate → run → fix → re-run
        )

        task_result = await agent.run(task=prompt)
        parsed = _parse_result(list(task_result.messages))

    await model_client.close()
    return parsed
