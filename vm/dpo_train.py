"""DPO on top of run A_qa against looping (the VM port of notebook cell 22). Policy = the A_qa adapter, trainable;
reference = the same adapter frozen at its starting weights (reference log-probabilities are computed once, before
training). Loss: -log sigmoid(beta * ((pi_c - ref_c) - (pi_r - ref_r))). Settings as A_dpo: beta 0.1, lr 1e-5, 2 epochs,
8 pairs per optimizer step, 3 warm-up steps, cosine. Completion log-probabilities cover the assistant turn only.

    python vm/dpo_train.py --src-adapter ~/checkpoints/A_qa-51/adapter --pairs pairs.jsonl --out ~/checkpoints/A_qa_dpo
"""
import argparse
import json
import math
import os
import random
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from peft import PeftModel, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ap = argparse.ArgumentParser()
ap.add_argument("--src-adapter", required=True)
ap.add_argument("--pairs", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--beta", type=float, default=0.1)
ap.add_argument("--lr", type=float, default=1e-5)
ap.add_argument("--epochs", type=int, default=2)
ap.add_argument("--accum", type=int, default=8)
ap.add_argument("--warmup", type=int, default=3)
ap.add_argument("--max-length", type=int, default=4096)
ap.add_argument("--seed", type=int, default=3407)
a = ap.parse_args()

out = Path(a.out).expanduser()
out.mkdir(parents=True, exist_ok=False)
random.seed(a.seed)
torch.manual_seed(a.seed)
if not torch.cuda.is_available():
    raise RuntimeError("the Slurm job has no usable GPU")

base = Path("/storage/tracka/models/base_model_path.txt").read_text().strip()
tok = AutoTokenizer.from_pretrained(base, local_files_only=True)


def ids_of(encoded):
    return list(encoded["input_ids"]) if hasattr(encoded, "get") else list(encoded)


pairs = [json.loads(line) for line in open(os.path.expanduser(a.pairs), encoding="utf-8") if line.strip()]
pairs = [p for p in pairs if p["n_tokens"] <= a.max_length]
print(f"pairs {len(pairs)}", flush=True)

quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                           bnb_4bit_compute_dtype=torch.bfloat16)
model = AutoModelForCausalLM.from_pretrained(base, local_files_only=True, quantization_config=quant,
                                             device_map={"": 0}, dtype=torch.bfloat16)
model.config.use_cache = False
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
model = PeftModel.from_pretrained(model, os.path.expanduser(a.src_adapter), is_trainable=True)
model.print_trainable_parameters()


def completion_logp(prompt, completion):
    """Sum of log-probabilities of the assistant turn `completion` given `prompt` (chat messages)."""
    prefix = ids_of(tok.apply_chat_template(prompt, tokenize=True, add_generation_prompt=True))
    full = ids_of(tok.apply_chat_template(prompt + [{"role": "assistant", "content": completion}], tokenize=True,
                                          add_generation_prompt=False))
    x = torch.tensor([full], device="cuda:0")
    logits = model(input_ids=x, attention_mask=torch.ones_like(x)).logits[0, :-1].float()
    targets = x[0, 1:]
    logp = torch.log_softmax(logits, dim=-1).gather(-1, targets[:, None])[:, 0]
    mask = torch.zeros_like(logp)
    mask[len(prefix) - 1:] = 1.0
    return (logp * mask).sum()


# reference: the starting adapter, frozen (computed once, before any update)
model.eval()
ref = []
with torch.no_grad():
    for p in pairs:
        ref.append((completion_logp(p["prompt"], p["chosen"][0]["content"]).item(),
                    completion_logp(p["prompt"], p["rejected"][0]["content"]).item()))
print(f"reference log-probabilities computed for {len(ref)} pairs", flush=True)

params = [q for q in model.parameters() if q.requires_grad]
opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=0.0)
total_steps = math.ceil(len(pairs) * a.epochs / a.accum)


def lr_at(step):
    if step < a.warmup:
        return a.lr * (step + 1) / a.warmup
    t = (step - a.warmup) / max(1, total_steps - a.warmup)
    return a.lr * 0.5 * (1 + math.cos(math.pi * t))


order = []
for ep in range(a.epochs):
    idx = list(range(len(pairs)))
    random.Random(a.seed + ep).shuffle(idx)
    order += idx

model.train()
step, acc, n_acc, hits, losses, margins = 0, 0.0, 0, 0, [], []
t0 = time.time()
for k, i in enumerate(order, 1):
    p = pairs[i]
    rc, rr = ref[i]
    pc = completion_logp(p["prompt"], p["chosen"][0]["content"])
    pr = completion_logp(p["prompt"], p["rejected"][0]["content"])
    margin = a.beta * ((pc - rc) - (pr - rr))
    loss = -F.logsigmoid(margin)
    (loss / a.accum).backward()
    acc += loss.item()
    margins.append(margin.item())
    hits += int(margin.item() > 0)
    n_acc += 1
    if n_acc == a.accum or k == len(order):
        for g in opt.param_groups:
            g["lr"] = lr_at(step)
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        opt.zero_grad(set_to_none=True)
        step += 1
        losses.append(acc / n_acc)
        acc, n_acc = 0.0, 0
        if step == 1 or step % 5 == 0:
            el = time.time() - t0
            print(f"step {step}/{total_steps} loss {losses[-1]:.4f} reward_acc {hits / max(1, len(margins)):.2f} "
                  f"elapsed {el / 60:.1f} min eta {el / step * (total_steps - step) / 60:.0f} min", flush=True)

model.save_pretrained(out / "adapter")
json.dump(losses, open(out / "losses.json", "w"))
summary = dict(run="A_qa_dpo", from_adapter=a.src_adapter, pairs=len(pairs), steps=step, beta=a.beta, lr=a.lr,
               epochs=a.epochs, accum=a.accum, first_loss=losses[0], last_loss=losses[-1],
               reward_accuracy=round(hits / max(1, len(margins)), 3), minutes=round((time.time() - t0) / 60, 1))
json.dump(summary, open(out / "train_summary.json", "w"), indent=1)
print("saved", summary, flush=True)
