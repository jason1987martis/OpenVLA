from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List


DEFAULT_MODEL_NAME = "openvla/openvla-7b"
DEFAULT_ADAPTER_DIR = "openvla_dobot_lora"


def build_prompt(instruction: str) -> str:
    """Build the language prompt used for both training and inference."""
    return f"In: What action should the robot take to {instruction}?\nOut:"


def parse_action_text(output_text: str) -> List[float]:
    """
    Extract the first five numeric values from a generated action string.

    This parser is intentionally tolerant so that small formatting variations do not break inference.
    """
    matches = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", output_text)
    if len(matches) < 5:
        raise ValueError(
            "Could not parse five action values from model output. "
            f"Raw output was: {output_text!r}"
        )
    return [float(value) for value in matches[:5]]


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Run inference with a base OpenVLA model plus a Dobot LoRA adapter."
    )
    parser.add_argument(
        "--image",
        type=Path,
        required=True,
        help="Path to the input image.",
    )
    parser.add_argument(
        "--instruction",
        required=True,
        help="Language instruction to condition the model on.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_NAME,
        help="Base OpenVLA model name or local path.",
    )
    parser.add_argument(
        "--adapter",
        type=Path,
        default=script_dir / DEFAULT_ADAPTER_DIR,
        help="Path to the saved LoRA adapter directory.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=32,
        help="Maximum number of new tokens to generate.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="Device override. 'auto' chooses CUDA when available.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.image.is_file():
        raise FileNotFoundError(f"Image file not found: {args.image}")
    if not args.adapter.is_dir():
        raise FileNotFoundError(f"Adapter directory not found: {args.adapter}")

    # Delay heavy imports so `--help` works before dependencies are installed.
    import torch
    from peft import PeftModel
    from PIL import Image
    from transformers import AutoModelForVision2Seq, AutoProcessor

    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device

    if device == "cuda":
        model_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    else:
        model_dtype = torch.float32

    print(f"Loading processor from {args.model}...")
    processor = AutoProcessor.from_pretrained(args.model, trust_remote_code=True)
    if processor.tokenizer.pad_token_id is None:
        processor.tokenizer.pad_token = processor.tokenizer.eos_token

    print(f"Loading base model from {args.model}...")
    base_model = AutoModelForVision2Seq.from_pretrained(
        args.model,
        torch_dtype=model_dtype,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )

    print(f"Loading LoRA adapter from {args.adapter}...")
    model = PeftModel.from_pretrained(base_model, args.adapter)
    model = model.to(device)
    model.eval()

    with Image.open(args.image) as image_handle:
        image = image_handle.convert("RGB")

    prompt = build_prompt(args.instruction.strip())
    inputs = processor(text=prompt, images=image, return_tensors="pt")
    inputs = {name: tensor.to(device) for name, tensor in inputs.items()}
    inputs["pixel_values"] = inputs["pixel_values"].to(dtype=model_dtype)

    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=False,
            pad_token_id=processor.tokenizer.pad_token_id,
        )

    prompt_token_count = inputs["input_ids"].shape[1]
    generated_action_ids = generated_ids[0, prompt_token_count:]
    generated_text = processor.decode(generated_action_ids, skip_special_tokens=True).strip()
    parsed_action = parse_action_text(generated_text)

    print(f"Raw output: {generated_text}")
    print(f"Parsed action: {parsed_action}")


if __name__ == "__main__":
    main()
