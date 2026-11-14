"""QLoRA fine-tune for run A_qa on the course VM: run A's settings (LoRA r16, alpha 32, lr 2e-4, all linear layers,
2 epochs, 16 examples per optimizer step, cosine with 6 warm-up steps), on train_v2.jsonl (drafting + extraction + Q&A).

The loss covers the assistant turn only; rows longer than --max-length are dropped, not cut. The base model is
Qwen2.5-7B-Instruct in 4-bit, loaded exactly as the course starter loads it (vm starter train.py).

    python vm/train_qa.py --train trainset/out/train_v2.jsonl --out ~/checkpoints/A_qa-<jobid>
"""
import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ap = argparse.ArgumentParser()
ap.add_argument("--train", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--r", type=int, default=16)
ap.add_argument("--alpha", type=int, default=32)
ap.add_argument("--lr", type=float, default=2e-4)
ap.add_argument("--epochs", type=int, default=2)
ap.add_argument("--accum", type=int, default=16)
ap.add_argument("--max-length", type=int, default=6144)
ap.add_argument("--warmup", type=int, default=6)
ap.add_argument("--seed", type=int, default=3407)
ap.add_argument("--save-every", type=int, default=50)
a = ap.parse_args()

out = Path(a.out).expanduser()
out.mkdir(parents=True, exist_ok=False)
random.seed(a.seed)
torch.manual_seed(a.seed)
torch.cuda.manual_seed_all(a.seed)
if not torch.cuda.is_available():
    raise RuntimeError("the Slurm job has no usable GPU")

base = Path("/storage/tracka/models/base_model_path.txt").read_text().strip()
tok = AutoTokenizer.from_pretrained(base, local_files_only=True)
if tok.pad_token_id is None:
    tok.pad_token = tok.eos_token


def ids_of(encoded):
    return list(encoded["input_ids"]) if hasattr(encoded, "get") else list(encoded)


examples, skipped = [], 0
for line in open(a.train, encoding="utf-8"):
    if not line.strip():
        continue
    msgs = json.loads(line)["messages"]
    prefix = ids_of(tok.apply_chat_template(msgs[:-1], tokenize=True, add_generation_prompt=True))
    full = ids_of(tok.apply_chat_template(msgs, tokenize=True, add_generation_prompt=False))
    if len(full) > a.max_length:
        skipped += 1
        continue
    labels = [-100] * min(len(prefix), len(full)) + full[len(prefix):]
    if any(v != -100 for v in labels):
        examples.append((full, labels))
    else:
        skipped += 1
print(f"examples {len(examples)} | skipped {skipped} | max-length {a.max_length}", flush=True)

quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                           bnb_4bit_compute_dtype=torch.bfloat16)
model = AutoModelForCausalLM.from_pretrained(base, local_files_only=True, quantization_config=quant,
                                             device_map={"": 0}, dtype=torch.bfloat16)
model.config.use_cache = False
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
model = get_peft_model(model, LoraConfig(
    r=a.r, lora_alpha=a.alpha, lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
model.print_trainable_parameters()

params = [p for p in model.parameters() if p.requires_grad]
opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=0.0)
total_steps = math.ceil(len(examples) * a.epochs / a.accum)


def lr_at(step):
    if step < a.warmup:
        return a.lr * (step + 1) / a.warmup
    t = (step - a.warmup) / max(1, total_steps - a.warmup)
    return a.lr * 0.5 * (1 + math.cos(math.pi * t))


order = []
for ep in range(a.epochs):
    idx = list(range(len(examples)))
    random.Random(a.seed + ep).shuffle(idx)
    order += idx

model.train()
step, acc, n_acc, losses = 0, 0.0, 0, []
t0 = time.time()
for k, i in enumerate(order, 1):
    ids, labels = examples[i]
    x = torch.tensor([ids], device="cuda:0")
    y = torch.tensor([labels], device="cuda:0")
    loss = model(input_ids=x, attention_mask=torch.ones_like(x), labels=y).loss
    (loss / a.accum).backward()
    acc += loss.item()
    n_acc += 1
    if n_acc == a.accum or k == len(order):
        for g in opt.param_groups:
            g["lr"] = lr_at(step)
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        opt.zero_grad(set_to_none=True)
        step += 1
        mean = acc / n_acc
        losses.append(mean)
        acc, n_acc = 0.0, 0
        if step == 1 or step % 5 == 0:
            el = time.time() - t0
            eta = el / step * (total_steps - step)
            print(f"step {step}/{total_steps} loss {mean:.4f} lr {lr_at(step - 1):.2e} "
                  f"elapsed {el / 60:.1f} min eta {eta / 60:.0f} min "
                  f"gpu {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)
        if step % a.save_every == 0:
            model.save_pretrained(out / f"ckpt-{step}")

model.save_pretrained(out / "adapter")
tok.save_pretrained(out / "adapter")
json.dump(losses, open(out / "losses.json", "w"))
summary = dict(run="A_qa", base="Qwen/Qwen2.5-7B-Instruct", train=a.train, examples=len(examples), skipped=skipped,
               steps=step, r=a.r, alpha=a.alpha, lr=a.lr, epochs=a.epochs, accum=a.accum, seed=a.seed,
               first_loss=losses[0], last_loss=losses[-1], minutes=round((time.time() - t0) / 60, 1),
               adapter=str(out / "adapter"))
json.dump(summary, open(out / "train_summary.json", "w"), indent=1)
print("saved", summary, flush=True)
