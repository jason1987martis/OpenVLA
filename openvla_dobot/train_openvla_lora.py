from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Sequence


DEFAULT_MODEL_NAME = "openvla/openvla-7b"
DEFAULT_OUTPUT_DIR = "openvla_dobot_lora"


def build_prompt(instruction: str) -> str:
    """Build the language prompt used for both training and inference."""
    return f"In: What action should the robot take to {instruction}?\nOut:"


def format_action_text(action: Sequence[float]) -> str:
    """Convert a 5D action vector into the requested comma-separated text."""
    if len(action) != 5:
        raise ValueError(f"Expected 5 action values, but received {len(action)}.")
    return ",".join(f"{float(value):.3f}" for value in action)


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Fine-tune OpenVLA with LoRA on a Dobot image/instruction/action dataset."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=script_dir / "dobot_dataset_example.json",
        help="Path to the dataset JSON file.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_NAME,
        help="Base OpenVLA model name or local path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=script_dir / DEFAULT_OUTPUT_DIR,
        help="Directory where the LoRA adapter will be saved.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=1,
        help="Number of passes over the dataset.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Training batch size. The scaffold defaults to batch size 1.",
    )
    parser.add_argument(
        "--grad-accumulation-steps",
        type=int,
        default=8,
        help="Number of gradient accumulation steps.",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=5e-5,
        help="Learning rate for AdamW.",
    )
    parser.add_argument(
        "--weight-decay",
        type=float,
        default=0.0,
        help="Weight decay for AdamW.",
    )
    parser.add_argument(
        "--max-text-length",
        type=int,
        default=256,
        help="Maximum tokenized text length for prompt plus action target.",
    )
    parser.add_argument(
        "--lora-rank",
        type=int,
        default=16,
        help="LoRA rank.",
    )
    parser.add_argument(
        "--lora-alpha",
        type=int,
        default=16,
        help="LoRA alpha scaling value.",
    )
    parser.add_argument(
        "--lora-dropout",
        type=float,
        default=0.05,
        help="LoRA dropout.",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=0,
        help="Optionally save the adapter every N optimizer steps. Set 0 to disable interim saves.",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=0,
        help="Number of DataLoader workers.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed.",
    )
    return parser.parse_args()


def validate_positive_int(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0, but received {value}.")


def choose_mixed_precision(torch_module) -> str:
    """Pick a reasonable mixed precision mode for the current CUDA device."""
    if torch_module.cuda.is_bf16_supported():
        return "bf16"
    return "fp16"


def choose_model_dtype(torch_module):
    """Choose the model weights dtype used for loading OpenVLA."""
    if torch_module.cuda.is_bf16_supported():
        return torch_module.bfloat16
    return torch_module.float16


def read_json_dataset(dataset_path: Path) -> List[dict]:
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    with dataset_path.open("r", encoding="utf-8") as handle:
        samples = json.load(handle)

    if not isinstance(samples, list) or not samples:
        raise ValueError("Dataset JSON must be a non-empty list of samples.")

    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ValueError(f"Sample {index} must be a JSON object.")

        for key in ("image", "instruction", "action"):
            if key not in sample:
                raise ValueError(f"Sample {index} is missing required key: {key}")

        if not isinstance(sample["instruction"], str) or not sample["instruction"].strip():
            raise ValueError(f"Sample {index} must contain a non-empty string instruction.")

        if not isinstance(sample["image"], str) or not sample["image"].strip():
            raise ValueError(f"Sample {index} must contain a non-empty image path string.")

        if not isinstance(sample["action"], list):
            raise ValueError(f"Sample {index} action must be a list of 5 numbers.")

        if len(sample["action"]) != 5:
            raise ValueError(f"Sample {index} action must contain 5 values.")

        for action_value in sample["action"]:
            if not isinstance(action_value, (int, float)):
                raise ValueError(f"Sample {index} action contains a non-numeric value: {action_value!r}")

    return samples


def main() -> None:
    args = parse_args()

    validate_positive_int("epochs", args.epochs)
    validate_positive_int("batch_size", args.batch_size)
    validate_positive_int("grad_accumulation_steps", args.grad_accumulation_steps)
    validate_positive_int("max_text_length", args.max_text_length)

    # Delay heavy imports until after argparse so `--help` works even before dependencies are installed.
    import torch
    from accelerate import Accelerator
    from peft import LoraConfig, get_peft_model
    from PIL import Image
    from torch.nn.utils.rnn import pad_sequence
    from torch.optim import AdamW
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForVision2Seq, AutoProcessor, set_seed

    if not torch.cuda.is_available():
        raise SystemExit(
            "CUDA is required for this training scaffold. "
            "OpenVLA-7B fine-tuning is not supported on CPU here."
        )

    dataset_path = args.dataset.resolve()
    output_dir = args.output_dir.resolve()
    samples = read_json_dataset(dataset_path)
    dataset_root = dataset_path.parent

    set_seed(args.seed)

    accelerator = Accelerator(gradient_accumulation_steps=args.grad_accumulation_steps, mixed_precision=choose_mixed_precision(torch))
    model_dtype = choose_model_dtype(torch)

    print(f"Loading processor from {args.model}...")
    processor = AutoProcessor.from_pretrained(args.model, trust_remote_code=True)

    # OpenVLA tokenizers do not always ship with a pad token. Reuse EOS for padding.
    if processor.tokenizer.pad_token_id is None:
        processor.tokenizer.pad_token = processor.tokenizer.eos_token

    print(f"Loading model from {args.model}...")
    model = AutoModelForVision2Seq.from_pretrained(
        args.model,
        torch_dtype=model_dtype,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )
    model.config.use_cache = False

    lora_config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        init_lora_weights="gaussian",
    )
    model = get_peft_model(model, lora_config)

    if accelerator.is_main_process:
        model.print_trainable_parameters()

    class DobotActionDataset(Dataset):
        """Simple JSON-backed dataset for image, instruction, and action supervision."""

        def __init__(self, raw_samples: Sequence[dict]) -> None:
            self.samples = list(raw_samples)

        def __len__(self) -> int:
            return len(self.samples)

        def _resolve_image_path(self, image_value: str) -> Path:
            image_path = Path(image_value)
            if not image_path.is_absolute():
                image_path = dataset_root / image_path
            return image_path

        def __getitem__(self, index: int) -> dict:
            sample = self.samples[index]
            image_path = self._resolve_image_path(sample["image"])

            if not image_path.is_file():
                raise FileNotFoundError(f"Image file not found for sample {index}: {image_path}")

            with Image.open(image_path) as image_handle:
                image = image_handle.convert("RGB")

            prompt = build_prompt(sample["instruction"].strip())
            action_text = format_action_text(sample["action"])
            full_text = prompt + action_text

            encoded = processor(
                text=full_text,
                images=image,
                return_tensors="pt",
                truncation=False,
            )

            # Tokenize the target text separately so we can mask the prompt tokens and only learn the action string.
            target_tokens = processor.tokenizer(
                action_text,
                add_special_tokens=False,
                return_tensors="pt",
            )

            input_ids = encoded["input_ids"].squeeze(0)
            attention_mask = encoded["attention_mask"].squeeze(0)
            pixel_values = encoded["pixel_values"].squeeze(0)
            labels = input_ids.clone()

            if input_ids.numel() > args.max_text_length:
                raise ValueError(
                    f"Sample {index} tokenized to {input_ids.numel()} tokens, which exceeds "
                    f"--max-text-length={args.max_text_length}. Shorten the instruction or raise the limit."
                )

            target_length = int(target_tokens["input_ids"].shape[-1])
            if target_length <= 0:
                raise ValueError(f"Sample {index} produced an empty target token sequence.")
            if target_length >= labels.numel():
                raise ValueError(
                    "The target consumed the whole token sequence. "
                    "Increase --max-text-length or shorten the instruction."
                )

            # Everything before the target is ignored in the loss.
            labels[:-target_length] = -100

            return {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "pixel_values": pixel_values,
                "labels": labels,
            }

    def collate_fn(batch: Iterable[dict]) -> dict:
        batch = list(batch)
        input_ids = pad_sequence(
            [item["input_ids"] for item in batch],
            batch_first=True,
            padding_value=processor.tokenizer.pad_token_id,
        )
        attention_mask = pad_sequence(
            [item["attention_mask"] for item in batch],
            batch_first=True,
            padding_value=0,
        )
        labels = pad_sequence(
            [item["labels"] for item in batch],
            batch_first=True,
            padding_value=-100,
        )
        pixel_values = torch.stack([item["pixel_values"] for item in batch])

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "pixel_values": pixel_values,
            "labels": labels,
        }

    train_dataset = DobotActionDataset(samples)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        collate_fn=collate_fn,
    )

    optimizer = AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    model, optimizer, train_loader = accelerator.prepare(model, optimizer, train_loader)

    output_dir.mkdir(parents=True, exist_ok=True)
    optimizer_step = 0

    print("Starting training...")
    for epoch_index in range(args.epochs):
        model.train()
        running_loss = 0.0

        for batch_index, batch in enumerate(train_loader, start=1):
            with accelerator.accumulate(model):
                batch["pixel_values"] = batch["pixel_values"].to(dtype=model_dtype)
                outputs = model(
                    input_ids=batch["input_ids"],
                    attention_mask=batch["attention_mask"],
                    pixel_values=batch["pixel_values"],
                    labels=batch["labels"],
                )
                loss = outputs.loss
                accelerator.backward(loss)

                if accelerator.sync_gradients:
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    optimizer_step += 1

                    if args.save_every > 0 and optimizer_step % args.save_every == 0:
                        accelerator.wait_for_everyone()
                        if accelerator.is_main_process:
                            interim_dir = output_dir / f"step_{optimizer_step}"
                            accelerator.unwrap_model(model).save_pretrained(interim_dir)
                            print(f"Saved interim adapter to {interim_dir}")

            running_loss += float(loss.detach().item())

            if accelerator.is_main_process:
                print(
                    f"Epoch {epoch_index + 1}/{args.epochs} | "
                    f"Batch {batch_index}/{len(train_loader)} | "
                    f"Loss {loss.detach().item():.6f}"
                )

        epoch_loss = running_loss / max(len(train_loader), 1)
        if accelerator.is_main_process:
            print(f"Finished epoch {epoch_index + 1}. Average loss: {epoch_loss:.6f}")

    accelerator.wait_for_everyone()
    if accelerator.is_main_process:
        accelerator.unwrap_model(model).save_pretrained(output_dir)
        print(f"Saved LoRA adapter to {output_dir}")


if __name__ == "__main__":
    main()
