import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from litellm import acompletion

from agent_factory.config import validate_llm_setup

MAX_TOOL_ROUNDS = 25
_PYTHON_TO_JSON_TYPE = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
}


@dataclass
class AgentConfig:
    model: str
    system_instructions: str
    tools: List[Callable[..., Any]] = field(default_factory=list)


class ChatResponse:
    def __init__(self, text: str):
        self._text = text

    async def text(self) -> str:
        return self._text


def _annotation_to_schema(annotation: Any) -> dict:
    if annotation is inspect.Parameter.empty:
        return {"type": "string"}

    origin = getattr(annotation, "__origin__", None)
    if origin is list:
        args = getattr(annotation, "__args__", ())
        item_type = args[0] if args else str
        return {
            "type": "array",
            "items": {"type": _PYTHON_TO_JSON_TYPE.get(item_type, "string")},
        }

    return {"type": _PYTHON_TO_JSON_TYPE.get(annotation, "string")}


def _function_to_tool(func: Callable[..., Any]) -> dict:
    sig = inspect.signature(func)
    properties = {}
    required = []

    for name, param in sig.parameters.items():
        if param.default is inspect.Parameter.empty:
            required.append(name)
        properties[name] = _annotation_to_schema(param.annotation)

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": (func.__doc__ or func.__name__).strip(),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def _execute_tool(func: Callable[..., Any], arguments: str) -> str:
    try:
        kwargs = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as exc:
        return f"Error parsing tool arguments: {exc}"

    try:
        result = func(**kwargs)
    except TypeError as exc:
        return f"Error calling tool {func.__name__}: {exc}"
    except Exception as exc:
        return f"Tool {func.__name__} failed: {exc}"

    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False)
    return str(result)


def _tool_arguments_to_str(arguments: Any) -> str:
    if arguments is None:
        return "{}"
    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments)


def _assistant_message_to_dict(message: Any) -> dict:
    payload = {"role": "assistant", "content": message.content or ""}
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        payload["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": getattr(tool_call, "type", "function") or "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": _tool_arguments_to_str(tool_call.function.arguments),
                },
            }
            for tool_call in tool_calls
        ]
    return payload


class Agent:
    """Provider-agnostic LLM agent with optional tool calling (via LiteLLM)."""

    def __init__(self, config: AgentConfig):
        self._config = config
        self._messages: List[dict] = []
        self._tool_map: dict[str, Callable[..., Any]] = {}
        self._started = False

    async def __aenter__(self) -> "Agent":
        ok, error = validate_llm_setup(self._config.model)
        if not ok:
            raise RuntimeError(error)

        self._messages = [{"role": "system", "content": self._config.system_instructions}]
        self._tool_map = {tool.__name__: tool for tool in self._config.tools}
        self._started = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._started = False

    async def chat(self, prompt: str) -> ChatResponse:
        if not self._started:
            raise RuntimeError("Agent session not started. Use 'async with Agent(...)'.")

        self._messages.append({"role": "user", "content": prompt})
        tools = [_function_to_tool(tool) for tool in self._config.tools]

        for _ in range(MAX_TOOL_ROUNDS):
            request_kwargs = {
                "model": self._config.model,
                "messages": self._messages,
                "drop_params": True,
            }
            if tools:
                request_kwargs["tools"] = tools

            response = await acompletion(**request_kwargs)
            message = response.choices[0].message
            self._messages.append(_assistant_message_to_dict(message))

            tool_calls = getattr(message, "tool_calls", None) or []
            if not tool_calls:
                return ChatResponse(message.content or "")

            for tool_call in tool_calls:
                func = self._tool_map.get(tool_call.function.name)
                if func is None:
                    tool_result = f"Unknown tool: {tool_call.function.name}"
                else:
                    tool_result = _execute_tool(
                        func,
                        _tool_arguments_to_str(tool_call.function.arguments),
                    )

                self._messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    }
                )

        return ChatResponse("Error: maximum tool call rounds exceeded.")
