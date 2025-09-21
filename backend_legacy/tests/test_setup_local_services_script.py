from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "setup_local_services.sh"


def run_setup(tmp_path: Path, *extra_args: str) -> tuple[Path, Path]:
    """Run the setup script constrained to env generation."""

    workspace = tmp_path / "workspace"
    env_source = tmp_path / "custom.env"
    env_source.write_text("POSTGRES_PORT=5432\n")

    cmd = [
        "bash",
        str(SCRIPT_PATH),
        "--workspace",
        str(workspace),
        "--env-source",
        str(env_source),
        "--components",
        "env",
        *extra_args,
    ]

    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
    return workspace, env_source


def test_env_only_generates_local_file(tmp_path):
    workspace, _ = run_setup(tmp_path)
    env_file = workspace / ".env.local"
    assert env_file.exists(), "Local environment file was not generated"

    content = env_file.read_text()
    assert "POSTGRES_HOST=127.0.0.1" in content
    assert "KEYCLOAK_URL=http://127.0.0.1:8180" in content


def test_validation_mode_for_env(tmp_path):
    workspace, env_source = run_setup(tmp_path)

    subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--workspace",
            str(workspace),
            "--env-source",
            str(env_source),
            "--components",
            "env",
            "--validate",
        ],
        check=True,
        cwd=PROJECT_ROOT,
        env={**os.environ},
    )

