"""OpenWorld Unified Interactive Playground & AI Agent Sandbox.

Combines:
1. Interactive World Sandbox (God Mode / Manual CLI): Create agents, set graphs,
   trigger weather, transfer resources, send signals, inspect memory, and verify
   cryptographic replays.
2. AI Agent Brain (Natural Language / LLM): Connects agents to Gemini, OpenAI,
   local Ollama, or built-in heuristic reasoning. Agents perceive the world, consult
   their HyperMemory, think, dialogue, and act autonomously.

Usage:
    python examples/interactive_playground.py
    python examples/interactive_playground.py --help
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.error
import urllib.request

# Ensure src is in python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openworld_superkernel.hyper_memory_p1e import HyperMemoryP1e, Observation as MemoryObservation
from openworld_superkernel.memory_contracts import MemoryEvent, Provenance
from openworld_superkernel.trust_boundaries import CapabilityAuthority
from openworld_superkernel.world_fixture import (
    Action, Agent, Observation as WorldObservation, StepResult, TickInput, Weather, World,
    advance, create_world, verify_replay,
)
from openworld_superkernel.world_guard import AuthorizedWorldAction, GuardedWorldGateway


# ==============================================================================
# AI Provider Backends (Gemini, OpenAI, Ollama, Heuristic)
# ==============================================================================

class AIBrain:
    """Pluggable AI Brain supporting Gemini, OpenAI, Ollama, and Heuristic rule fallback."""

    def __init__(self, provider: str = "heuristic", model: Optional[str] = None, api_key: Optional[str] = None):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")

        if self.provider == "gemini" and not self.model:
            self.model = "gemini-1.5-flash"
        elif self.provider == "openai" and not self.model:
            self.model = "gpt-4o-mini"
        elif self.provider == "ollama" and not self.model:
            self.model = "llama3"

    def think_and_act(
        self,
        agent_id: str,
        owner_id: str,
        observation: WorldObservation,
        memories: List[Dict[str, Any]],
        prediction_p: float,
        prompt: str,
    ) -> Dict[str, Any]:
        """Generate structured reasoning, dialogue, and an action."""
        context = {
            "agent_id": agent_id,
            "owner_id": owner_id,
            "current_tick": observation.tick,
            "balance": observation.balance,
            "region": observation.region,
            "weather": observation.weather,
            "neighbors": list(observation.neighbors),
            "inbox_signals": list(observation.inbox),
            "estimated_success_prob": round(prediction_p, 4),
            "recent_memories": memories[-5:],
            "user_goal": prompt,
        }

        if self.provider == "gemini" and self.api_key:
            return self._call_gemini(context)
        elif self.provider == "openai" and self.api_key:
            return self._call_openai(context)
        elif self.provider == "ollama":
            return self._call_ollama(context)
        else:
            return self._call_heuristic(context)

    def _system_prompt(self) -> str:
        return (
            "You are an autonomous AI Agent in OpenWorld. "
            "You must return ONLY a valid JSON object with the following keys:\n"
            '{\n'
            '  "thought": "Your internal strategic thinking based on memory and world state",\n'
            '  "message": "What you say out loud to other agents or overseer",\n'
            '  "action": "transfer" | "signal" | "hold",\n'
            '  "target": "neighbor_agent_id" or null,\n'
            '  "amount": integer amount (1 if transfer, 0 otherwise)\n'
            '}'
        )

    def _call_gemini(self, context: Dict[str, Any]) -> Dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        user_text = f"{self._system_prompt()}\n\nCurrent Situation:\n{json.dumps(context, indent=2)}"
        req_body = {
            "contents": [{"parts": [{"text": user_text}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(req_body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
        except Exception as e:
            return self._fallback_error(f"Gemini API error: {e}", context)

    def _call_openai(self, context: Dict[str, Any]) -> Dict[str, Any]:
        url = "https://api.openai.com/v1/chat/completions"
        user_text = f"Current Situation:\n{json.dumps(context, indent=2)}"
        req_body = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": user_text},
            ],
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(req_body).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["choices"][0]["message"]["content"]
                return json.loads(text)
        except Exception as e:
            return self._fallback_error(f"OpenAI API error: {e}", context)

    def _call_ollama(self, context: Dict[str, Any]) -> Dict[str, Any]:
        url = "http://localhost:11434/api/generate"
        prompt = f"{self._system_prompt()}\n\nCurrent Situation:\n{json.dumps(context, indent=2)}\n\nRespond in JSON:"
        req_body = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(req_body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return json.loads(data["response"])
        except Exception as e:
            return self._fallback_error(f"Ollama local error: {e}", context)

    def _call_heuristic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic offline rule-based reasoning engine."""
        neighbors = context["neighbors"]
        balance = context["balance"]
        prob = context["estimated_success_prob"]
        target = neighbors[0] if neighbors else None
        user_goal = context.get("user_goal", "").lower()

        if not target:
            return {
                "thought": "I have no connected neighbors to interact with.",
                "message": "Standing by, isolated from other agents.",
                "action": "hold",
                "target": None,
                "amount": 0,
            }

        # Strategic decision based on goal and memory
        if "signal" in user_goal or "chao" in user_goal or "hello" in user_goal:
            return {
                "thought": f"The goal specifies communication. Sending signal to {target}.",
                "message": f"Hello {target}! Broadcasting signal from {context['region']}.",
                "action": "signal",
                "target": target,
                "amount": 0,
            }
        elif balance >= 2 and prob >= 0.4:
            return {
                "thought": f"Balance ({balance}) is healthy and success probability ({prob:.2f}) is favorable. Proposing resource transfer to {target}.",
                "message": f"Hey {target}, offering 1 resource to cooperate.",
                "action": "transfer",
                "target": target,
                "amount": 1,
            }
        elif balance < 2:
            return {
                "thought": f"Low balance ({balance}). Need to preserve resources. Signaling neighbor {target}.",
                "message": f"Hey {target}, my resources are running low. Let's synchronize.",
                "action": "signal",
                "target": target,
                "amount": 0,
            }
        else:
            return {
                "thought": f"Holding position to assess situation. Success probability ({prob:.2f}) requires caution.",
                "message": "Holding action for this cycle.",
                "action": "hold",
                "target": None,
                "amount": 0,
            }

    def _fallback_error(self, err_msg: str, context: Dict[str, Any]) -> Dict[str, Any]:
        res = self._call_heuristic(context)
        res["thought"] = f"[{err_msg}] Falling back to heuristic: {res['thought']}"
        return res


# ==============================================================================
# Playground Environment State Manager
# ==============================================================================

class PlaygroundWorld:
    """High-level facade over OpenWorld SuperKernel, HyperMemory, and Guarded Gateway."""

    def __init__(self, db_path: Optional[str] = None):
        self.temp_dir: Optional[tempfile.TemporaryDirectory] = None
        if db_path is None:
            self.temp_dir = tempfile.TemporaryDirectory(prefix="openworld-playground-", ignore_cleanup_errors=True)
            self.db_path = str(Path(self.temp_dir.name) / "playground-memory.sqlite3")
        else:
            self.temp_dir = None
            self.db_path = db_path

        self.memory = HyperMemoryP1e(Path(self.db_path))
        self.principal = "playground-overseer"
        self.authority = CapabilityAuthority(
            os.urandom(32), issuer="playground-authority", audience="world"
        )
        self.gateway = GuardedWorldGateway(
            self.authority, authenticated_principal=lambda: self.principal
        )
        self.ai = AIBrain(provider="heuristic")

        # Initial world genesis
        self.agents_dict: Dict[str, Agent] = {
            "alice": Agent("alice", "owner1", "north", 5),
            "bob": Agent("bob", "owner1", "south", 5),
        }
        self.edges_set: set[Tuple[str, str]] = {("alice", "bob")}
        self.genesis: World = self._build_world()
        self.current_world: World = self.genesis
        self.pending_actions: List[AuthorizedWorldAction] = []
        self.pending_weather: List[Weather] = []

    def close(self) -> None:
        try:
            if hasattr(self, "memory") and self.memory:
                self.memory.close()
        except Exception:
            pass
        try:
            if self.temp_dir:
                self.temp_dir.cleanup()
        except Exception:
            pass

    def __del__(self) -> None:
        self.close()

    def _build_world(self, seed: int = 2026) -> World:
        agents = tuple(self.agents_dict.values())
        edges = tuple(self.edges_set)
        return create_world(agents, edges, seed=seed)

    def reset(self) -> None:
        self.genesis = self._build_world()
        self.current_world = self.genesis
        self.pending_actions.clear()
        self.pending_weather.clear()

    def get_token(self, agent_id: str, action: str) -> str:
        owner = self.agents_dict[agent_id].owner_id
        now = int(time.time())
        return self.authority.issue(
            principal=self.principal,
            owner=owner,
            resource=agent_id,
            action=action,
            valid_from=now - 10,
            expires_at=now + 600,
        )

    def add_agent(self, agent_id: str, balance: int = 5, region: str = "mid", owner: str = "owner1") -> None:
        if agent_id in self.agents_dict:
            raise ValueError(f"Agent '{agent_id}' already exists.")
        self.agents_dict[agent_id] = Agent(agent_id, owner, region, balance)
        # Re-genesis needed when agent structure changes
        self.reset()

    def connect(self, agent1: str, agent2: str) -> None:
        if agent1 not in self.agents_dict or agent2 not in self.agents_dict:
            raise ValueError("Both agents must exist to connect.")
        edge = (agent1, agent2) if agent1 < agent2 else (agent2, agent1)
        self.edges_set.add(edge)
        self.reset()

    def set_weather(self, region: str, condition: str) -> None:
        if condition not in ("clear", "rain"):
            raise ValueError("Weather condition must be 'clear' or 'rain'.")
        self.pending_weather.append(Weather(region, condition))

    def observe(self, agent_id: str) -> WorldObservation:
        read_token = self.get_token(agent_id, "read_world")
        return self.gateway.observe(self.current_world, agent_id=agent_id, signed_capability=read_token)

    def get_prediction(self, agent_id: str) -> Tuple[float, str]:
        owner = self.agents_dict[agent_id].owner_id
        return self.memory.predict(owner_id=owner, agent_id=agent_id, requester_owner_id=owner)

    def queue_action(self, actor: str, target: str, kind: str, amount: int = 0) -> str:
        if actor not in self.agents_dict:
            raise ValueError(f"Actor '{actor}' not found.")
        if target not in self.agents_dict:
            raise ValueError(f"Target '{target}' not found.")
        if kind not in ("transfer", "signal"):
            raise ValueError("Action kind must be 'transfer' or 'signal'.")

        write_token = self.get_token(actor, "write_agent")
        req_id = f"cmd-{self.current_world.tick}-{actor}-{len(self.pending_actions)}"
        owner = self.agents_dict[actor].owner_id
        act = Action(
            request_id=req_id,
            tick=self.current_world.tick,
            principal=owner,
            actor=actor,
            target=target,
            kind=kind,
            amount=amount if kind == "transfer" else 0,
        )
        self.pending_actions.append(AuthorizedWorldAction(act, write_token))
        return req_id

    def tick(self) -> StepResult:
        """Advance the world by 1 tick, applying queued actions and weather."""
        actions_tuple = tuple(self.pending_actions)
        weather_tuple = tuple(self.pending_weather)
        self.pending_actions.clear()
        self.pending_weather.clear()

        step = self.gateway.advance(
            self.current_world,
            actions=actions_tuple,
            external=weather_tuple,
            max_actions=len(actions_tuple) + 10,
        )
        old_world = self.current_world
        self.current_world = step.world

        # Update agents_dict balances from current_world
        balance_map = dict(self.current_world.balances)
        for aid, agent in list(self.agents_dict.items()):
            if aid in balance_map:
                self.agents_dict[aid] = Agent(
                    agent.agent_id, agent.owner_id, agent.region, balance_map[aid]
                )

        # Record events to HyperMemory
        for action_wrap in actions_tuple:
            act = action_wrap.action
            if act.request_id in step.accepted:
                owner = self.agents_dict[act.actor].owner_id
                mem_state = self.memory.get_state(owner_id=owner, agent_id=act.actor, requester_owner_id=owner)
                event_id = f"mem-{self.current_world.tick}-{act.actor}-{act.request_id}"
                outcome = 1  # Success
                payload = json.dumps({
                    "tick": self.current_world.tick,
                    "action": act.kind,
                    "actor": act.actor,
                    "target": act.target,
                    "amount": act.amount,
                    "outcome": outcome,
                    "world_fingerprint": self.current_world.fingerprint(),
                }).encode("utf-8")

                self.memory.apply_batch(
                    (
                        MemoryObservation(
                            event=MemoryEvent(
                                event_id=event_id,
                                owner_id=owner,
                                event_type="action_result",
                                provenance=Provenance.SIMULATED,
                                payload=payload,
                                protected=True,
                            ),
                            agent_id=act.actor,
                            sequence_number=mem_state["seq"] + 1,
                            outcome=outcome,
                        ),
                    ),
                    requester_owner_id=owner,
                )

        return step

    def ask_agent(self, agent_id: str, prompt: str) -> Dict[str, Any]:
        """Ask the agent's AI brain to reason about a goal."""
        obs = self.observe(agent_id)
        pred, _ = self.get_prediction(agent_id)
        owner = self.agents_dict[agent_id].owner_id
        mem_state = self.memory.get_state(owner_id=owner, agent_id=agent_id, requester_owner_id=owner)
        memories = [
            {"seq": mem_state["seq"], "successes": mem_state["successes"], "n": mem_state["n"]}
        ]
        return self.ai.think_and_act(
            agent_id=agent_id,
            owner_id=owner,
            observation=obs,
            memories=memories,
            prediction_p=pred,
            prompt=prompt,
        )

    def act_with_ai(self, agent_id: str, prompt: str) -> Tuple[Dict[str, Any], StepResult]:
        """AI plans an action and immediately executes it into the world."""
        decision = self.ask_agent(agent_id, prompt)
        action_kind = decision.get("action", "hold")
        target = decision.get("target")
        amount = int(decision.get("amount", 1 if action_kind == "transfer" else 0))

        if action_kind in ("transfer", "signal") and target:
            self.queue_action(agent_id, target, action_kind, amount)

        step = self.tick()
        return decision, step

    def verify_chain(self) -> bool:
        return verify_replay(self.genesis, self.current_world)


# ==============================================================================
# Interactive REPL Shell Interface
# ==============================================================================

BANNER = r"""
===============================================================================
       ___                     _       __           _     __
      / _ \ _ __   ___ _ __   | |     / /___  _____| |___/ /
     / // /| '_ \ / _ \ '_ \  | | /| / // _ \/ ___/ / __  / 
    / // / | |_) |  __/ | | | | |/ |/ // (_) / /  / / /_/ /  
   /____/  | .__/ \___/_| |_| |__/|__/ \___//_/  /_/\__,_/   
           |_|                                               
   UNIFIED INTERACTIVE PLAYGROUND & AI AGENT SANDBOX (R0 + LLM)
===============================================================================
 Type 'help' or '?' to see the list of commands. Type 'exit' to quit.
"""

HELP_TEXT = """
============================== COMMAND REFERENCE ==============================
MANUAL SANDBOX (GOD MODE):
  status | ls                      - View all agents, balances, graph, and weather
  create <name> [bal] [reg] [own]  - Spawn a new agent (e.g. 'create charlie 10 mid')
  connect <agent1> <agent2>        - Link 2 agents with an edge (e.g. 'connect alice bob')
  weather <region> <clear|rain>    - Set weather (e.g. 'weather north rain')
  transfer <from> <to> [amount]    - Queue a transfer (e.g. 'transfer alice bob 1')
  signal <from> <to>               - Queue a communication signal (e.g. 'signal bob alice')
  tick | step                      - Advance world by 1 tick & execute queued actions
  history                          - Show all accepted events and fingerprints
  memory <agent>                   - Inspect an agent's HyperMemory & success probability
  replay                           - Verify cryptographic SHA-256 state chain
  reset                            - Reset world back to genesis

AI AGENT BRAIN (NATURAL LANGUAGE):
  set-ai <heuristic|gemini|openai|ollama> [model_or_key]
                                   - Switch AI backend (default: heuristic)
  ask <agent> <your prompt/goal>   - Ask agent to reason & respond using its AI brain
  act <agent> <your prompt/goal>   - Ask agent to think AND immediately execute action!
  auto [agent] [ticks]             - Run autonomous think-and-act loop for N ticks

MISCELLANEOUS:
  help | ?                         - Show this help manual
  exit | quit                      - Exit playground
===============================================================================
"""


def execute_command(pw: PlaygroundWorld, line: str) -> bool:
    """Execute a single playground command. Returns False if exiting."""
    parts = shlex.split(line)
    if not parts:
        return True
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd in ("exit", "quit"):
        print("Goodbye!")
        return False

    elif cmd in ("help", "?"):
        print(HELP_TEXT)

    elif cmd in ("status", "ls"):
        print(f"\n--- World State [Tick {pw.current_world.tick}] ---")
        print(f"Fingerprint: {pw.current_world.fingerprint()[:16]}...")
        print("\nAGENTS:")
        print(f" {'ID':<12} | {'OWNER':<10} | {'REGION':<8} | {'BALANCE':<8} | {'NEIGHBORS'}")
        print("-" * 65)
        for aid, agent in pw.agents_dict.items():
            obs = pw.observe(aid)
            neighbors = ", ".join(obs.neighbors) or "(none)"
            print(f" {aid:<12} | {agent.owner_id:<10} | {agent.region:<8} | {agent.resources:<8} | {neighbors}")
        print("\nWEATHER:")
        for reg, cond in pw.current_world.weather:
            print(f"  * Region {reg}: {cond}")
        if pw.pending_actions:
            print(f"\nPENDING ACTIONS ({len(pw.pending_actions)} queued):")
            for p in pw.pending_actions:
                print(f"  - {p.action.actor} -> {p.action.kind} -> {p.action.target} (amount: {p.action.amount})")
        print()

    elif cmd == "create":
        if not args:
            print("Usage: create <name> [balance=5] [region=mid] [owner=owner1]")
            return True
        name = args[0]
        bal = int(args[1]) if len(args) > 1 else 5
        reg = args[2] if len(args) > 2 else "mid"
        owner = args[3] if len(args) > 3 else "owner1"
        pw.add_agent(name, bal, reg, owner)
        print(f"[+] Agent '{name}' created with balance {bal} in region '{reg}' (World reset to new genesis).")

    elif cmd == "connect":
        if len(args) < 2:
            print("Usage: connect <agent1> <agent2>")
            return True
        pw.connect(args[0], args[1])
        print(f"[+] Connected edge between '{args[0]}' and '{args[1]}'.")

    elif cmd == "weather":
        if len(args) < 2:
            print("Usage: weather <region> <clear|rain>")
            return True
        pw.set_weather(args[0], args[1])
        print(f"[+] Weather change queued for {args[0]}: {args[1]}")

    elif cmd == "transfer":
        if len(args) < 2:
            print("Usage: transfer <from> <to> [amount=1]")
            return True
        amt = int(args[2]) if len(args) > 2 else 1
        req_id = pw.queue_action(args[0], args[1], "transfer", amt)
        print(f"[+] Queued transfer of {amt} from '{args[0]}' to '{args[1]}' (Req: {req_id}). Type 'tick' to execute.")

    elif cmd == "signal":
        if len(args) < 2:
            print("Usage: signal <from> <to>")
            return True
        req_id = pw.queue_action(args[0], args[1], "signal", 0)
        print(f"[+] Queued signal from '{args[0]}' to '{args[1]}' (Req: {req_id}). Type 'tick' to execute.")

    elif cmd in ("tick", "step"):
        step = pw.tick()
        print(f"[>>>] Advanced to Tick {pw.current_world.tick}.")
        if step.accepted:
            print(f"  Accepted ({len(step.accepted)}): {', '.join(step.accepted)}")
        if step.rejected:
            print(f"  Rejected ({len(step.rejected)}): {step.rejected}")

    elif cmd == "memory":
        if not args:
            print("Usage: memory <agent_id>")
            return True
        aid = args[0]
        if aid not in pw.agents_dict:
            print(f"Error: Unknown agent '{aid}'")
            return True
        owner = pw.agents_dict[aid].owner_id
        state = pw.memory.get_state(owner_id=owner, agent_id=aid, requester_owner_id=owner)
        pred, est = pw.get_prediction(aid)
        print(f"\n--- HyperMemory for Agent '{aid}' ---")
        print(f"  Owner:                {owner}")
        print(f"  Total Observations:   {state['n']}")
        print(f"  Recorded Successes:   {state['successes']}")
        print(f"  Current Sequence:     {state['seq']}")
        print(f"  Active Estimator:     {est}")
        print(f"  Success Probability:  {pred:.4f}")
        print()

    elif cmd == "history":
        print(f"\n--- Event Log ({len(pw.current_world.events)} events) ---")
        for e in pw.current_world.events:
            print(f"  Tick {e.tick} | Seq {e.sequence} | {e.actor} -> {e.kind} -> {e.target} (amt: {e.amount}) [{e.provenance}]")
        print()

    elif cmd == "replay":
        ok = pw.verify_chain()
        print(f"[Replay Check] Genesis -> Tick {pw.current_world.tick}: {'PASS' if ok else 'FAILED'}")
        print(f"Current SHA-256 Digest: {pw.current_world.fingerprint()}")

    elif cmd == "reset":
        pw.reset()
        print("[!] World reset to initial Genesis state.")

    elif cmd == "set-ai":
        if not args:
            print("Usage: set-ai <heuristic|gemini|openai|ollama> [model_or_api_key]")
            return True
        prov = args[0]
        extra = args[1] if len(args) > 1 else None
        if prov == "gemini":
            pw.ai = AIBrain("gemini", api_key=extra)
        elif prov == "openai":
            pw.ai = AIBrain("openai", api_key=extra)
        elif prov == "ollama":
            pw.ai = AIBrain("ollama", model=extra or "llama3")
        else:
            pw.ai = AIBrain("heuristic")
        print(f"[AI] AI backend changed to: {pw.ai.provider.upper()} ({pw.ai.model or 'default'})")

    elif cmd == "ask":
        if len(args) < 2:
            print("Usage: ask <agent> <question or prompt>")
            return True
        aid = args[0]
        prompt = " ".join(args[1:])
        if aid not in pw.agents_dict:
            print(f"Error: Unknown agent '{aid}'")
            return True
        print(f"\n[AI Thinking] Agent '{aid}' is analyzing world & memory...")
        decision = pw.ask_agent(aid, prompt)
        print(f"  Thought:  {decision.get('thought')}")
        print(f"  Message:  \"{decision.get('message')}\"")
        print(f"  Proposal: Action={decision.get('action')}, Target={decision.get('target')}, Amount={decision.get('amount')}\n")

    elif cmd == "act":
        if len(args) < 2:
            print("Usage: act <agent> <instruction/goal>")
            return True
        aid = args[0]
        prompt = " ".join(args[1:])
        if aid not in pw.agents_dict:
            print(f"Error: Unknown agent '{aid}'")
            return True
        print(f"\n[AI Action] Agent '{aid}' thinking & executing...")
        decision, step = pw.act_with_ai(aid, prompt)
        print(f"  Thought:  {decision.get('thought')}")
        print(f"  Message:  \"{decision.get('message')}\"")
        print(f"  Executed: Action={decision.get('action')}, Target={decision.get('target')}, Amount={decision.get('amount')}")
        print(f"  Result:   Tick={step.world.tick}, Accepted={step.accepted}, Replay={'PASS' if pw.verify_chain() else 'FAIL'}\n")

    elif cmd == "auto":
        aid = args[0] if len(args) > 0 and args[0] in pw.agents_dict else "alice"
        ticks = int(args[1]) if len(args) > 1 else (int(args[0]) if len(args) > 0 and args[0].isdigit() else 3)
        print(f"\n--- Running Autonomous Loop: Agent '{aid}' for {ticks} ticks ---")
        for i in range(ticks):
            print(f"--- Cycle {i + 1}/{ticks} (Tick {pw.current_world.tick}) ---")
            dec, step = pw.act_with_ai(aid, "Survive, build trust, and balance resources")
            print(f"  [{aid}] Thought: {dec.get('thought')}")
            print(f"  [{aid}] Said:    \"{dec.get('message')}\"")
            print(f"  [{aid}] Action:  {dec.get('action')} -> {dec.get('target')}")
        print(f"[Done] Finished autonomous loop. Current Tick: {pw.current_world.tick}\n")

    else:
        print(f"Unknown command: '{cmd}'. Type 'help' for available commands.")

    return True


def run_repl(pw: PlaygroundWorld) -> None:
    print(BANNER)
    print(f"[OK] World initialized at Tick {pw.current_world.tick} with {len(pw.agents_dict)} agents.")
    print(f"[AI] Active AI Backend: {pw.ai.provider.upper()} ({pw.ai.model or 'default'})")
    print("-------------------------------------------------------------------------------")

    while True:
        try:
            line = input(f"OpenWorld [T:{pw.current_world.tick}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting OpenWorld Playground.")
            break

        if not line:
            continue

        try:
            if not execute_command(pw, line):
                break
        except Exception as e:
            print(f"[Error] {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenWorld Interactive Playground & AI Agent Sandbox")
    parser.add_argument("--script", type=str, help="Path to text file containing commands to execute")
    parser.add_argument("--auto", type=int, help="Automatically run N ticks of autonomous AI cycle")
    args = parser.parse_args()

    pw = PlaygroundWorld()
    try:
        if args.auto:
            print(f"Running automated simulation for {args.auto} ticks...")
            for i in range(args.auto):
                pw.act_with_ai("alice", "maintain balance with neighbor")
            print(f"Completed! Final Tick: {pw.current_world.tick}, Replay: {pw.verify_chain()}")
        elif args.script:
            script_path = Path(args.script)
            if not script_path.exists():
                print(f"Error: Script file '{args.script}' not found.")
                sys.exit(1)
            with open(script_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        print(f"\n>>> [SCRIPT] {line}")
                        if not execute_command(pw, line):
                            break
        else:
            run_repl(pw)
    finally:
        pw.close()


if __name__ == "__main__":
    main()
