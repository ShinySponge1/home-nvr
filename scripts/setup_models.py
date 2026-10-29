#!/usr/bin/env python3
"""Print or explicitly pull the generated config's official pretrained Qwen model.

Does not start services, train models, change Frigate configuration, or read
camera images. Ollama's existing Docker service must already be running.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

from bootstrap import InventoryError, SUPPORTED_VISION_MODELS, UniqueKeyLoader, yaml


def pull_command(project_dir):
    config_path = Path(project_dir) / "config/frigate.yml"
    if not config_path.is_file() or config_path.stat().st_size > 1024 * 1024:
        raise InventoryError("Generate a valid project config/frigate.yml before setting up a model.")
    try:
        config = yaml.load(config_path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise InventoryError("Generated Frigate configuration is invalid YAML.") from exc
    providers = config.get("genai") if isinstance(config, dict) else None
    if not isinstance(providers, dict) or not providers:
        raise InventoryError("Enable ai.enabled in the inventory and regenerate configuration before setting up a model.")
    models = []
    for provider in providers.values():
        if not isinstance(provider, dict) or provider.get("provider") != "ollama" or provider.get("model") not in SUPPORTED_VISION_MODELS:
            raise InventoryError("Model setup accepts only the documented official Qwen3-VL instruct tags.")
        models.append(provider["model"])
    if len(set(models)) != 1:
        raise InventoryError("Generated AI providers must agree on one public model tag.")
    # Read the canonical generated provider config, never a separate .env model
    # override, URL, arbitrary registry, local file, or user checkpoint.
    return ["docker", "compose", "--profile", "ai", "exec", "-T", "ollama", "ollama", "pull", models[0]]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pull", action="store_true", help="Explicitly download the public model into the running Ollama service's Docker volume.")
    args = parser.parse_args(argv)
    try:
        project = args.project_dir.resolve()
        if not (project / "compose.yaml").is_file():
            raise InventoryError("Project directory must contain compose.yaml.")
        command = pull_command(project)
        print("Planned public pretrained model command: " + " ".join(command))
        if args.pull:
            subprocess.run(command, cwd=project, check=True)
        else:
            print("No download performed. Start the project's Ollama service, then repeat with --pull.")
    except (InventoryError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"Model setup failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
