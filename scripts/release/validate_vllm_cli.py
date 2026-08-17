#!/usr/bin/env python3
"""Validate the pinned vLLM serve parser without probing build-host hardware."""
from __future__ import annotations

import json
from argparse import ArgumentParser
from importlib.metadata import version


EXPECTED_VLLM_VERSION = "0.25.1"
REQUIRED_SERVE_FLAGS = (
    "--api-key",
    "--code-revision",
    "--disable-log-stats",
    "--dtype",
    "--generation-config",
    "--gpu-memory-utilization",
    "--host",
    "--max-model-len",
    "--max-num-seqs",
    "--no-enable-prefix-caching",
    "--port",
    "--reasoning-parser",
    "--reasoning-parser-plugin",
    "--revision",
    "--served-model-name",
    "--tokenizer-revision",
    "--trust-remote-code",
)


def validate_version(observed_version: str) -> None:
    if observed_version != EXPECTED_VLLM_VERSION:
        raise RuntimeError(
            f"Expected vLLM {EXPECTED_VLLM_VERSION}, found {observed_version}"
        )


def validate_parser(parser: ArgumentParser) -> list[str]:
    options = {
        option
        for action in parser._actions
        for option in getattr(action, "option_strings", ())
    }
    missing = sorted(set(REQUIRED_SERVE_FLAGS) - options)
    if missing:
        raise RuntimeError(f"Pinned vLLM serve parser is missing flags: {missing}")
    return sorted(options)


def _build_parser_without_hardware_probe() -> ArgumentParser:
    # vLLM constructs DeviceConfig defaults while building its argparse parser.
    # A GPU-less image builder therefore cannot even render `vllm serve --help`.
    # vLLM's own top-level CLI uses CpuPlatform for GPU-independent parser
    # handling. Apply the same process-local fallback before importing the
    # dedicated documentation parser; no server, model, or device is touched.
    from vllm import platforms
    from vllm.platforms.cpu import CpuPlatform

    platforms.current_platform = CpuPlatform()
    from vllm.entrypoints.openai.cli_args import create_parser_for_docs

    return create_parser_for_docs()


def main() -> int:
    observed_version = version("vllm")
    validate_version(observed_version)
    options = validate_parser(_build_parser_without_hardware_probe())
    print(
        json.dumps(
            {
                "passed": True,
                "vllm_version": observed_version,
                "required_flags": list(REQUIRED_SERVE_FLAGS),
                "serve_option_count": len(options),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
