from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .external import validate_external
from .infer import infer_pipeline
from .io_load import ROOT, load_config, load_main, write_data_profile, write_json
from .leakage import leakage_report
from .preprocess import preprocess_main
from .train import prepare_full, train_pipeline
from .validate import validate_pipeline


def _configure_logging(config: dict) -> None:
    report_dir = ROOT / config["project"]["reports_dir"]
    report_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(report_dir / "run.log", encoding="utf-8")],
        force=True,
    )


def _load_preprocessed(config: dict):
    raw, metadata = load_main(config)
    processed, stats = preprocess_main(raw, config)
    logging.getLogger(__name__).info("Loaded %s (%s): %s", metadata["path"], metadata["encoding"], stats)
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="DIVE 2026 six-type classification pipeline")
    parser.add_argument("--stage", choices=["profile", "label", "train", "validate", "leakage", "infer", "all"], default="all")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    _configure_logging(config)
    validate_external(config)
    if args.stage in {"profile", "all"}:
        path = write_data_profile(config)
        logging.info("Wrote %s", path)
        if args.stage == "profile":
            return

    raw = _load_preprocessed(config)
    if args.stage == "label":
        _, _, q, labels = prepare_full(raw, config)
        artifacts = ROOT / config["project"]["artifacts_dir"]
        labels.to_parquet(artifacts / "labels.parquet", index=False)
        write_json(artifacts / "quantiles.json", {"full": q, "folds": []})
        logging.info("Wrote labels and full-data quantiles")
        return
    if args.stage in {"train", "all"}:
        train_pipeline(raw, config)
        if args.stage == "train":
            return
    if args.stage in {"validate", "all"}:
        path = validate_pipeline(raw, config)
        logging.info("Wrote %s", path)
        if args.stage == "validate":
            return
    if args.stage in {"leakage", "all"}:
        path = leakage_report(raw, config)
        logging.info("Wrote %s", path)
        if args.stage == "leakage":
            return
    if args.stage in {"infer", "all"}:
        path = infer_pipeline(raw, config)
        logging.info("Wrote %s", path)


if __name__ == "__main__":
    main()
