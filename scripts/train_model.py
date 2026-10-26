import argparse
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from app.core.config import Settings
from app.data.databricks_client import DatabricksClient
from app.data.export_cache import load_export
from app.data.training_repository import TemporalPlan, TrainingRepository, temporal_split
from app.ml.artifacts import persist
from app.ml.fixtures import FIXTURE_PLAN, synthetic_frame
from app.ml.selection import freeze_selection
from app.ml.training import train


def main():
    parser = argparse.ArgumentParser(description="Explicit fixture or bounded read-only training")
    parser.add_argument("--source", choices=["fixture", "databricks"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", type=Path, help="JSON: temporal plan + measured capacity")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--cache-directory", type=Path, help="Existing private immutable real export"
    )
    args = parser.parse_args()
    try:
        code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except subprocess.CalledProcessError:
        code_sha = "uncommitted-fixture-only"
    if args.source == "fixture":
        partitions = temporal_split(synthetic_frame(seed=args.seed), FIXTURE_PLAN)
        reference = {
            "source": "synthetic_fixture_only",
            "seed": args.seed,
            "temporal_plan": asdict(FIXTURE_PLAN),
        }
    else:
        if not args.plan:
            parser.error("Databricks mode requires --plan with measured capacity evidence")
        if (
            code_sha == "uncommitted-fixture-only"
            or subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=normal"], text=True
            ).strip()
        ):
            parser.error("Real training requires an exact clean code commit")
        config = json.loads(args.plan.read_text(encoding="utf-8"))
        evidence = config["capacity_evidence"]
        required = {
            "pilot_rows",
            "pilot_bytes",
            "peak_rss_bytes",
            "available_ram_bytes",
            "reserved_ram_bytes",
            "measured_at",
            "host",
            "code_sha",
        }
        if not required.issubset(evidence) or evidence["code_sha"] != code_sha:
            parser.error("Measured pilot capacity evidence for this code SHA required")
        for name in required - {"measured_at", "host", "code_sha"}:
            if type(evidence[name]) is not int or evidence[name] <= 0:
                parser.error("Capacity measurements must be positive integers")
        remaining = evidence["available_ram_bytes"] - evidence["reserved_ram_bytes"]
        capacity = int(remaining / (evidence["peak_rss_bytes"] / evidence["pilot_rows"]))
        total_budget = config["train_budget"] + 2 * config["evaluation_budget"]
        if remaining <= 0 or total_budget > capacity or config["max_bytes"] > remaining:
            parser.error("Requested export exceeds measured capacity with reserve")
        if args.cache_directory:
            partitions, reference = load_export(
                args.cache_directory, config=config, seed=args.seed, code_sha=code_sha
            )
        else:
            settings = Settings()
            partitions, reference = TrainingRepository(
                DatabricksClient(settings), settings
            ).extract(
                TemporalPlan(**config["temporal_plan"]),
                version=config["version"],
                train_budget=config["train_budget"],
                evaluation_budget=config["evaluation_budget"],
                max_bytes=config["max_bytes"],
                seed=args.seed,
                evaluation_sample=config.get("evaluation_sample", False),
            )
        reference["capacity_evidence"] = evidence
        reference["evaluation_status"] = (
            "Historical v12 dates were already explored; not new independent future evidence"
        )
    pipeline, metadata = train(
        partitions,
        reference=reference,
        code_sha=code_sha,
        synthetic=args.source == "fixture",
        seed=args.seed,
        freeze_callback=(
            (
                lambda model, selection: freeze_selection(
                    args.output.with_name(args.output.name + "-selection"), model, selection
                )
            )
            if args.source == "databricks"
            else None
        ),
    )
    persist(args.output, pipeline, metadata)
    print(
        json.dumps(
            {
                "artifact": str(args.output),
                "synthetic": metadata.synthetic,
                "model_type": metadata.model_type,
                "threshold": metadata.threshold,
            }
        )
    )


if __name__ == "__main__":
    main()
