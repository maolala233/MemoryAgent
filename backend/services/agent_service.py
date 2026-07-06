"""Agent registry + execution with retrieval-augmented prompts."""
from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from ..database import db
from ..utils.logger import info, warn
from .config_loader import get_agents_config
from .llm_adapter import LLMFactory, LLMProvider
from .retrieval_service import retriever, SearchStrategy


class Tool:
    """Agent tool definitions (callable from prompts)."""

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description


class Agent:
    """Single agent instance bound to an LLM provider."""

    def __init__(self, config: Dict[str, Any], llm: LLMProvider) -> None:
        self.config = config
        self.llm = llm
        self.id = config.get("id", "agent")
        self.name = config.get("name", self.id)
        self.role = config.get("role", "")
        self.description = config.get("description", "")
        self.system_prompt = config.get("system_prompt", "")
        self.memory_strategy = config.get("memory_strategy", SearchStrategy.HYBRID)
        self.memory_limit = int(config.get("memory_limit", 5))
        self.tools = config.get("tools", [])

    async def retrieve_memories(self, task: str) -> List[Dict[str, Any]]:
        if self.memory_strategy == SearchStrategy.NONE:
            return []
        return await retriever.search(
            task, strategy=self.memory_strategy, limit=self.memory_limit
        )

    def _build_prompt(self, task: str,
                      memories: List[Dict[str, Any]],
                      context: Optional[List[Dict[str, Any]]] = None) -> str:
        parts = []
        if memories:
            parts.append("## Retrieved memories\n")
            for m in memories:
                parts.append(
                    f"- [memory: {m['rel_path']}] (score {m.get('score', 0)}) "
                    f"{m.get('title', '')}\n  {m.get('snippet', '')[:300]}\n"
                )
        if context:
            parts.append("\n## Conversation history\n")
            for msg in context[-6:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                parts.append(f"**{role}**: {content}\n")
        parts.append("\n## Current task\n")
        parts.append(task)
        return "\n".join(parts)

    async def run(self, task: str,
                  context: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        memories = await self.retrieve_memories(task)
        prompt = self._build_prompt(task, memories, context)
        response = await self.llm.generate(prompt, self.system_prompt)
        return {"response": response, "memories": memories, "thinking": None}

    async def stream_run(self, task: str,
                         context: Optional[List[Dict[str, Any]]] = None
                         ) -> AsyncIterator[Dict[str, Any]]:
        memories = await self.retrieve_memories(task)
        yield {"type": "memories", "content": memories}
        yield {"type": "thinking", "content": f"Retrieved {len(memories)} memories using '{self.memory_strategy}' strategy."}
        prompt = self._build_prompt(task, memories, context)
        async for token in self.llm.stream_generate(prompt, self.system_prompt):
            yield {"type": "chunk", "content": token}
        yield {"type": "done", "content": ""}


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: Dict[str, Agent] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}

    def load(self) -> None:
        cfg = get_agents_config()
        agents = cfg.get("agents", [])
        for entry in agents:
            agent_id = entry.get("id") or entry.get("name", "agent").lower().replace(" ", "-")
            entry["id"] = agent_id
            self._configs[agent_id] = entry
        info(f"Loaded {len(self._configs)} agent configs")

    def list_agents(self) -> List[Dict[str, Any]]:
        if not self._configs:
            self.load()
        return list(self._configs.values())

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        if not self._configs:
            self.load()
        if agent_id in self._agents:
            return self._agents[agent_id]
        cfg = self._configs.get(agent_id)
        if not cfg:
            # Fuzzy match by name
            for cid, c in self._configs.items():
                if c.get("name", "").lower().replace(" ", "-") == agent_id.lower():
                    cfg = c
                    agent_id = cid
                    break
        if not cfg:
            return None
        llm = LLMFactory.create(cfg.get("llm_provider"), cfg.get("llm_model"))
        agent = Agent(cfg, llm)
        self._agents[agent_id] = agent
        return agent


class AgentService:
    def __init__(self) -> None:
        self.registry = AgentRegistry()

    def ensure_loaded(self) -> None:
        if not self.registry._configs:
            self.registry.load()

    def list_agents(self) -> List[Dict[str, Any]]:
        self.ensure_loaded()
        return self.registry.list_agents()

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        self.ensure_loaded()
        return self.registry.get_agent(agent_id)

    async def run_agent(self, agent_id: str, message: str,
                        context: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Unknown agent: {agent_id}")
        result = await agent.run(message, context=context)
        db.save_message(agent_id, "user", message)
        db.save_message(
            agent_id, "assistant", result["response"],
            memories=result.get("memories"), thinking=result.get("thinking"),
        )
        return result

    async def stream_agent(self, agent_id: str, message: str,
                           context: Optional[List[Dict[str, Any]]] = None
                           ) -> AsyncIterator[Dict[str, Any]]:
        agent = self.get_agent(agent_id)
        if not agent:
            yield {"type": "error", "content": f"Unknown agent: {agent_id}"}
            return
        db.save_message(agent_id, "user", message)
        full_text = ""
        memories: List[Dict[str, Any]] = []
        async for event in agent.stream_run(message, context=context):
            if event["type"] == "memories":
                memories = event["content"]
                yield event
            elif event["type"] == "chunk":
                full_text += event["content"]
                yield event
            elif event["type"] == "thinking":
                yield event
            elif event["type"] == "done":
                db.save_message(agent_id, "assistant", full_text, memories=memories)
                yield {"type": "done", "content": "", "memories": memories}

    async def test_agent(self, agent_id: str, prompt: str) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            result = await self.run_agent(agent_id, prompt)
            latency = int((time.perf_counter() - start) * 1000)
            return {
                "response": result["response"],
                "latency_ms": latency,
                "status": "ok",
                "memories": result.get("memories", []),
            }
        except Exception as exc:
            warn(f"Agent test failed: {exc}")
            return {
                "response": f"Error: {exc}",
                "latency_ms": int((time.perf_counter() - start) * 1000),
                "status": "error",
            }


agent_service = AgentService()
