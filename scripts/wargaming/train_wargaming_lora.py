"""Unsloth QLoRA Fine-Tuning Script for Matt Mickey Wargaming Expert

Fine-tunes Qwen-2.5-7B-Instruct or Llama-3.1-8B-Instruct using Unsloth 4-bit QLoRA
on data/wargaming_sft.jsonl (08:30 AM EST pre-market ChatML dataset with ZERO look-ahead).

Outputs GGUF weights to data/wargaming-expert.gguf for Ollama serving.
"""
from __future__ import annotations

import os
import sys
import logging
import json
from pathlib import Path
import argparse

REPO_ROOT = Path(__file__).parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def train_wargaming_lora(
    base_model: str = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit",
    dataset_sft_path: str = "data/wargaming_sft.jsonl",
    dataset_eval_path: str = "data/wargaming_postmortem.jsonl",
    output_dir: str = "models/wargaming_lora",
    max_seq_length: int = 4096,
    r: int = 16,
    lora_alpha: int = 16,
    batch_size: int = 2,
    grad_accum: int = 4,
    epochs: int = 3,
    lr: float = 2e-4,
    quantization_gguf: str = "q4_k_m",
) -> Path:
    print(f"\n==========================================================================")
    print(f"   UNSLOTH QLORA FINE-TUNING ENGINE: WARGAMING EXPERT")
    print(f"   Base Model:        {base_model}")
    print(f"   SFT Dataset:       {dataset_sft_path}")
    print(f"   Evaluation Set:    {dataset_eval_path}")
    print(f"   Output Directory:  {output_dir}")
    print(f"==========================================================================")

    out_path = REPO_ROOT / output_dir
    out_path.mkdir(parents=True, exist_ok=True)
    gguf_path = REPO_ROOT / "data" / f"wargaming-expert-{quantization_gguf}.gguf"

    # Attempt Unsloth import
    try:
        from unsloth import FastLanguageModel
        import torch
        from datasets import load_dataset
        from trl import SFTTrainer
        from transformers import TrainingArguments

        log.info("Loaded Unsloth & FastLanguageModel successfully!")

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model,
            max_seq_length=max_seq_length,
            dtype=None,
            load_in_4bit=True,
        )

        model = FastLanguageModel.get_peft_model(
            model,
            r=r,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            lora_alpha=lora_alpha,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=3407,
            use_rslora=False,
            loftq_config=None,
        )

        # Load SFT dataset
        dataset = load_dataset("json", data_files={"train": str(REPO_ROOT / dataset_sft_path)})

        def format_chatml(examples):
            texts = []
            for messages in examples["messages"]:
                formatted = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
                texts.append(formatted)
            return {"text": texts}

        dataset = dataset.map(format_chatml, batched=True)

        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset["train"],
            dataset_text_field="text",
            max_seq_length=max_seq_length,
            dataset_num_proc=2,
            packing=False,
            args=TrainingArguments(
                per_device_train_batch_size=batch_size,
                gradient_accumulation_steps=grad_accum,
                warmup_ratio=0.05,
                num_train_epochs=epochs,
                learning_rate=lr,
                fp16=not torch.cuda.is_bf16_supported(),
                bf16=torch.cuda.is_bf16_supported(),
                logging_steps=1,
                optim="adamw_8bit",
                weight_decay=0.01,
                lr_scheduler_type="linear",
                seed=3407,
                output_dir=str(out_path),
            ),
        )

        log.info("Starting Unsloth QLoRA Training...")
        trainer.train()

        log.info("Saving LoRA Fine-Tuned Model to %s...", out_path)
        model.save_pretrained(str(out_path))
        tokenizer.save_pretrained(str(out_path))

        log.info("Exporting GGUF (%s) for Ollama...", quantization_gguf)
        model.save_pretrained_gguf(str(REPO_ROOT / "data" / "wargaming-expert"), tokenizer, quantization_method=quantization_gguf)
        print(f"\n🎉 GGUF Exported successfully to: {gguf_path}\n")

    except ImportError as ie:
        log.warning("Unsloth / Trl not installed in current environment (%s).", ie)
        log.info("Generating standalone CUDA fine-tuning recipe and config in %s.", output_dir)
        
        recipe = {
            "base_model": base_model,
            "sft_dataset": str(REPO_ROOT / dataset_sft_path),
            "eval_dataset": str(REPO_ROOT / dataset_eval_path),
            "lora_r": r,
            "lora_alpha": lora_alpha,
            "max_seq_length": max_seq_length,
            "epochs": epochs,
            "learning_rate": lr,
            "output_dir": str(out_path),
            "target_gguf": str(gguf_path),
        }
        with open(out_path / "training_recipe.json", "w", encoding="utf-8") as f:
            json.dump(recipe, f, indent=2)

    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unsloth QLoRA Fine-Tuning Script")
    parser.add_argument("--base-model", default="unsloth/Qwen2.5-7B-Instruct-bnb-4bit", help="HuggingFace base model")
    parser.add_argument("--sft-dataset", default="data/wargaming_sft.jsonl", help="Pre-market SFT ChatML dataset")
    parser.add_argument("--eval-dataset", default="data/wargaming_postmortem.jsonl", help="EOD post-mortem dataset")
    parser.add_argument("--output-dir", default="models/wargaming_lora", help="Output directory")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--gguf", default="q4_k_m", help="GGUF quantization format")
    args = parser.parse_args()

    train_wargaming_lora(
        base_model=args.base_model,
        dataset_sft_path=args.sft_dataset,
        dataset_eval_path=args.eval_dataset,
        output_dir=args.output_dir,
        epochs=args.epochs,
        quantization_gguf=args.gguf,
    )
