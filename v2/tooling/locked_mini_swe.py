"""mini-swe-agent (upstream harbor built-in, runs inside the sandbox) + model.patch capture,
for fresh-sandbox re-grading with patch_replay:PatchReplayAgent."""
from __future__ import annotations

from harbor.agents.installed.mini_swe_agent import MiniSweAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

_CAPTURE = (
    "pkill -f '[m]ini-swe-agent --yolo' >/dev/null 2>&1; sleep 3; "  # stop the agent so the trajectory file is not still being written when harbor tars /logs/agent
    "mkdir -p /logs/agent; "
    "repo=$(git -C /app rev-parse --show-toplevel 2>/dev/null || git -C /testbed rev-parse --show-toplevel 2>/dev/null || echo /app); "
    'cd "$repo" && git add -A 2>/dev/null; git diff --cached > /logs/agent/model.patch 2>/dev/null; git reset -q 2>/dev/null; '
    "wc -c < /logs/agent/model.patch; true"
)


class LockedMiniSwe(MiniSweAgent):
    @staticmethod
    def name() -> str:
        return "mini-swe-agent-locked"

    async def install(self, environment: BaseEnvironment) -> None:
        """Upstream installs against the image's system Python; on the Python-3.10 SWE-bench Pro
        images the newest litellm then fails to import (typing.NotRequired). Pin a managed 3.12."""
        try:
            await self.ensure_system_dependencies(
                environment, ("curl", "bash", "build_tools", "git", "python3", "python_pip"))
        except Exception as e:  # old Debian images (buster/bullseye): deb.debian.org no longer serves them -> retry via archive.debian.org
            self.logger.warning(f"apt install failed ({str(e)[:100]}); retrying against archive.debian.org")
            await environment.exec(command=(
                "sed -i -e 's|deb.debian.org/debian-security|archive.debian.org/debian-security|g' -e 's|security.debian.org|archive.debian.org|g' "
                "-e 's|deb.debian.org|archive.debian.org|g' -e '/buster-updates/d' -e '/bullseye-updates/d' /etc/apt/sources.list 2>/dev/null; "
                "echo 'Acquire::Check-Valid-Until \"false\";' > /etc/apt/conf.d/99no-check-valid 2>/dev/null || true; "
                "apt-get -o Acquire::Check-Valid-Until=false update >/dev/null 2>&1; "
                "apt-get install -y --no-install-recommends curl bash git python3 python3-pip build-essential >/dev/null 2>&1 || true"), user="root", timeout_sec=900)
            chk = await environment.exec(command="command -v curl && command -v git && command -v bash && echo TOOLS_OK", user="root", timeout_sec=60)
            if "TOOLS_OK" not in (chk.stdout or ""):
                raise
            self.logger.warning("required tools present after archive.debian.org retry; continuing")
        version_spec = f"=={self._version}" if self._version else ""
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                "if ! command -v uv >/dev/null 2>&1; then curl -LsSf https://astral.sh/uv/install.sh | sh; fi && "
                'if ! grep -q \'export PATH="$HOME/.local/bin:$PATH"\' "$HOME/.bashrc" 2>/dev/null; then'
                '  echo \'export PATH="$HOME/.local/bin:$PATH"\' >> "$HOME/.bashrc"; fi && '
                'if [ -f "$HOME/.local/bin/env" ]; then source "$HOME/.local/bin/env"; fi && '
                'export PATH="$HOME/.local/bin:$PATH" && '
                f"uv tool install --python 3.12 mini-swe-agent{version_spec} "
                "--with litellm --with orjson --with fastapi --with mcp && mini-swe-agent --help"
            ),
        )


    async def exec_as_agent(self, environment, command: str, **kw):
        """Wrap the mini-swe-agent invocation in an in-sandbox `timeout` (budget - 60 s) so the process
        always ends even if harbor's client-side timeout cannot cancel a stalled exec stream."""
        if "mini-swe-agent --yolo" in command:
            budget = int(getattr(self, "_timeout_sec", None) or 3000) - 60
            command = f"timeout -k 30 {budget} bash -c {__import__('shlex').quote(command)}"
        return await super().exec_as_agent(environment, command, **kw)

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        try:
            await super().run(instruction, environment, context)
        finally:
            try:
                r = await environment.exec(command=_CAPTURE, user="root", timeout_sec=300)
                self.logger.info(f"model.patch bytes: {(r.stdout or '').strip()}")
            except Exception as e:
                self.logger.warning(f"patch capture failed: {e}")
