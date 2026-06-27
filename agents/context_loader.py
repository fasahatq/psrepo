"""
ContextLoader — loads project-level and agent-level context for LLM calls.

Directory layout expected (relative to project root):
  context/
    project.md              ← always loaded; shared across all agents
    agents/
      segmentation.md
      prioritization.md
      dq.md
      msl.md
      <any-other-agent>.md

Usage:
    from agents.context_loader import ContextLoader

    ctx = ContextLoader()
    system_prompt = ctx.build("segmentation")   # project.md + agents/segmentation.md
    text = call_llm(prompt, api_key, model, system_prompt=system_prompt)
"""

import os
import logging

logger = logging.getLogger("perfect_store.context_loader")

# Project root is one level above this file (agents/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONTEXT_DIR  = os.path.join(_PROJECT_ROOT, "context")


class ContextLoader:
    """
    Loads and caches context files. Instantiate once per pipeline run.

    project.md is loaded on first call to build() and cached for the
    lifetime of the instance. Agent-specific files are also cached after
    their first load so repeated calls within one run incur no I/O.
    """

    def __init__(self, context_dir: str = None):
        self._dir     = context_dir or _CONTEXT_DIR
        self._cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self, agent_name: str) -> str:
        """
        Return a combined system-prompt string:
          [project context]
          ---
          [agent-specific context]

        Either section is omitted silently if its file is missing.
        """
        parts = []

        project = self._load("project.md")
        if project:
            parts.append(project)

        agent = self._load(os.path.join("agents", f"{agent_name}.md"))
        if agent:
            if parts:
                parts.append("---")
            parts.append(agent)

        if not parts:
            logger.warning(
                f"ContextLoader: no context files found for agent '{agent_name}' "
                f"(looked in {self._dir})"
            )
            return ""

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self, relative_path: str) -> str:
        """Load a file relative to context_dir, returning "" if absent."""
        if relative_path in self._cache:
            return self._cache[relative_path]

        full_path = os.path.join(self._dir, relative_path)
        if not os.path.exists(full_path):
            logger.debug(f"ContextLoader: file not found — {full_path}")
            self._cache[relative_path] = ""
            return ""

        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        logger.debug(f"ContextLoader: loaded {full_path} ({len(content)} chars)")
        self._cache[relative_path] = content
        return content
