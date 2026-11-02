"""Writes colab/sme_drhp_colab.ipynb (kept as a script so the notebook is reviewable as code) and the Drive package.

    python colab/make_notebook.py            # notebook + colab/sme_drhp_colab.zip (code + teacher jobs, no corpus)

Stages (PLAN.md sections 9-11). GPU stages run on Colab; building the rows runs on the laptop in between, because
it needs the 62,947 segmented train units (precedents, MinHash). Files move through MyDrive/sme_drhp/, which
Google Drive for desktop syncs to the laptop.
"""
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
cells = []


def md(s):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n")})


def code(s):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip("\n")})


md("""
# SME DRHP drafter: teacher extraction and QLoRA fine-tuning (Colab)

| stage | GPU | what it does | writes to `MyDrive/sme_drhp/` |
|---|---|---|---|
| 0 | any | unzip the package, install | – |
| 1 | A100 | **teacher screen**: two candidate teachers on 30 units | `screen/responses_<tag>.jsonl`, `screen/SCREEN_REPORT.md` |
| 2 | A100 | **full teacher extraction**, 2,062 calls, resumable | `work/teacher_responses.jsonl` |
| – | laptop | `python -m data.build rows` (gates, router, distractors, precedents, MinHash) | `out/train.jsonl`, `out/test.jsonl` |
| 3 | L4 | **baselines** B0/B1 on the test rows | `runs/B0`, `runs/B1` |
| 4 | L4 | **QLoRA runs** A and B (+ ablation 1, seeds) | `runs/<run>/adapter`, `runs/<run>/predictions_test.jsonl` |

Every stage is resumable: rerun a cell after a disconnect and it continues. Check the per-GPU unit rate in the
Resources panel before the first run, and disconnect the runtime when a stage finishes.
""")

md("## Stage 0: setup")
code("""
from google.colab import drive
drive.mount('/content/drive')
import os, subprocess, sys, json, time
DRIVE = '/content/drive/MyDrive/sme_drhp'
os.makedirs(DRIVE, exist_ok=True)
for d in ('screen', 'work', 'out', 'runs'):
    os.makedirs(f'{DRIVE}/{d}', exist_ok=True)
PKG = f'{DRIVE}/sme_drhp_colab.zip'
if not os.path.exists(PKG):
    # not on Drive yet: pick sme_drhp_drafter/colab/sme_drhp_colab.zip from your laptop; it is saved to Drive for next time
    from google.colab import files
    up = files.upload()
    name = next(iter(up))
    open(PKG, 'wb').write(up[name])
    print(f'saved {name} -> {PKG}')
!rm -rf /content/sme && mkdir -p /content/sme && unzip -q -o {PKG} -d /content/sme
assert os.path.exists('/content/sme/teacher/driver.py'), 'package did not unzip'
%cd /content/sme
sys.path.insert(0, '/content/sme')
!nvidia-smi --query-gpu=name,memory.total --format=csv
""")
code("""
# teacher serving (latest vLLM: Colab runs Python 3.13, which older pinned versions do not support)
# uv resolves and downloads far faster than pip and shows progress (pip -q can sit silently for 10+ minutes)
!pip install -q uv
!uv pip install --system "vllm==0.32.0" "httpx>=0.27" fastapi "pydantic>=2"   # installs on Colab (Python 3.13), 1 Nov 2026
!pip show vllm 2>/dev/null | head -2
""")

md("""
## Stage 1: teacher screen (A100)

Both candidates from PLAN.md read the same 30 units (`trainset/screen/screen_jobs.jsonl`). Upload your labels first:
fill `reviewer_labels.xlsx` (10 units) on the laptop, run `python -m teacher.label_sheet read --xlsx ...`, and copy
`reviewer_labels.json` to `MyDrive/sme_drhp/screen/`. Pass rule: precision >= 95% and coverage >= 85%.
""")
code("""
import os, sys, subprocess, json, time
DRIVE = '/content/drive/MyDrive/sme_drhp'     # this cell also runs alone in a fresh runtime, so set paths here
%cd /content/sme
sys.path.insert(0, '/content/sme')
from teacher.serving import candidates, gpu_gb, serve, stop   # serve/stop kill the whole vLLM tree between models
from teacher.driver import run
GPU_GB = gpu_gb()
CANDIDATES = candidates(GPU_GB)
print(f'GPU memory {GPU_GB:.0f} GB ->', {k: v['model'] for k, v in CANDIDATES.items()})
jobs = [json.loads(l) for l in open('trainset/screen/screen_jobs.jsonl', encoding='utf-8')]
for tag, c in CANDIDATES.items():
    out = f'{DRIVE}/screen/responses_{tag}.jsonl'
    p = serve(c['model'], c['args'])
    try:
        print(tag, run(jobs, out, 'http://localhost:8000/v1', c['model']))
    finally:
        stop(p)
""")
code("""
labels = f'{DRIVE}/screen/reviewer_labels.json'
lab = f'--labels {labels}' if os.path.exists(labels) else ''
!python -m teacher.screen score --responses {DRIVE}/screen/responses_qwen3_32b_awq.jsonl {DRIVE}/screen/responses_qwen3_30b_a3b.jsonl {lab}
!cp trainset/screen/SCREEN_REPORT.md {DRIVE}/screen/
""")

md("""
## Stage 2: full teacher extraction (resumable)

Set `TEACHER` to the candidate that passed the screen. 2,062 calls; rerun the cell after a disconnect and it skips
the units already answered. Then, on the laptop: `python -m data.build rows --responses <Drive>/work/teacher_responses.jsonl`
and copy `trainset/out/*.jsonl` to `MyDrive/sme_drhp/out/`.
""")
TEACHER_CELL = """
import os, sys, json
DRIVE = '/content/drive/MyDrive/sme_drhp'
%cd /content/sme
sys.path.insert(0, '/content/sme')
from teacher.serving import candidates, gpu_gb, serve, stop
from teacher.driver import run
TEACHER = 'qwen3_32b_awq'          # the candidate that passed SCREEN_REPORT.md (precision >= 95%, coverage >= 85%)
c = candidates(gpu_gb())[TEACHER]
jobs = [json.loads(l) for l in open('trainset/work/{jobs}', encoding='utf-8')]
p = serve(c['model'], c['args'])
try:
    print(run(jobs, f'{{DRIVE}}/work/{out}', 'http://localhost:8000/v1', c['model']))
finally:
    stop(p)
"""
code(TEACHER_CELL.format(jobs="teacher_jobs.jsonl", out="teacher_responses.jsonl"))

md("""
## Stage 2b: gap-fill (A100, about 500 short calls)

A second teacher pass for drafting units that failed the coverage gate: the prompt lists the figures, dates and names
the first pass missed (`trainset/work/gapfill_jobs.jsonl`, made on the laptop with `python -m teacher.gapfill jobs`).
Resumable like stage 2. Then, on the laptop: `python -m teacher.gapfill merge ...` and `python -m data.build rows`
on the merged responses (TRAINING.md).
""")
code(TEACHER_CELL.format(jobs="gapfill_jobs.jsonl", out="gapfill_responses.jsonl"))

md("""
## Stage 3-4: baselines and QLoRA (L4)

Student `Qwen/Qwen2.5-7B-Instruct`, 4-bit QLoRA with Unsloth, loss on the assistant turn only, `max_seq_len` 6,144.
Runs (PLAN.md 7.7): **A** r16 / lr 2e-4 / all linear layers / 2 epochs; **B** r64 / lr 1e-4; **C** r32 / lr 2e-4 /
3 epochs / drafting rows twice (added 1 Nov 2026: run A did not beat the base model on drafting); **ablation1** = best
config on `train_no_distractors.jsonl`; **seed2/seed3** = best config with other seeds. Each team member runs one.
A configuration counts as better only if its **held-out loss** on the test drafts beats the base model's (cell after
training); run the seed and ablation runs only once a configuration passes.
Set a `WANDB_API_KEY` Colab secret to log to Weights & Biases.
""")
code("""
!pip install -q uv
!uv pip install --system "unsloth" "trl>=0.19" "peft" "bitsandbytes" "datasets" "wandb"
# torchvision on the Colab image is built against Pillow 11.3.0; a newer Pillow breaks the Unsloth import
!uv pip install --system --reinstall "pillow==11.3.0"
!pip show unsloth trl torch vllm pillow 2>/dev/null | grep -E '^(Name|Version)'
# now Runtime > Restart session, then run stage 0 again and continue from the next cell
""")
code("""
RUNS = {
    'A':         dict(r=16, alpha=32, lr=2e-4, epochs=2, data='train.jsonl', seed=3407),
    'B':         dict(r=64, alpha=64, lr=1e-4, epochs=2, data='train.jsonl', seed=3407),
    'C':         dict(r=32, alpha=64, lr=2e-4, epochs=3, data='train.jsonl', seed=3407, draft_weight=2),
    'ablation1': dict(r=16, alpha=32, lr=2e-4, epochs=2, data='train_no_distractors.jsonl', seed=3407),
    'seed2':     dict(r=16, alpha=32, lr=2e-4, epochs=2, data='train.jsonl', seed=11),
    'seed3':     dict(r=16, alpha=32, lr=2e-4, epochs=2, data='train.jsonl', seed=23),
}
RUN = 'A'                       # change per team member
BASE = 'Qwen/Qwen2.5-7B-Instruct'
MAX_SEQ = 6144
cfg = RUNS[RUN]
out_dir = f'{DRIVE}/runs/{RUN}'
os.makedirs(out_dir, exist_ok=True)
try:
    from google.colab import userdata
    os.environ['WANDB_API_KEY'] = userdata.get('WANDB_API_KEY'); report = 'wandb'
except Exception:
    report = 'none'
""")
code("""
from unsloth import FastLanguageModel
from unsloth.chat_templates import train_on_responses_only
from datasets import Dataset
from trl import SFTTrainer, SFTConfig

model, tok = FastLanguageModel.from_pretrained(BASE, max_seq_length=MAX_SEQ, load_in_4bit=True)
model = FastLanguageModel.get_peft_model(model, r=cfg['r'], lora_alpha=cfg['alpha'], lora_dropout=0.0,
    target_modules=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'],
    use_gradient_checkpointing='unsloth', random_state=cfg['seed'])
rows = [json.loads(l) for l in open(f"{DRIVE}/out/{cfg['data']}", encoding='utf-8')]
rows += [r for r in rows if r['metadata']['skill'] == 'drafting'] * (cfg.get('draft_weight', 1) - 1)
ds = Dataset.from_list([{'text': tok.apply_chat_template(r['messages'], tokenize=False)} for r in rows])
# checkpoints on Drive so a disconnect can resume; TRL >= 0.20 renamed max_seq_length to max_length
ckpt_dir = f'{out_dir}/ckpt'
seq_kw = 'max_length' if 'max_length' in SFTConfig.__dataclass_fields__ else 'max_seq_length'
trainer = SFTTrainer(model=model, processing_class=tok, train_dataset=ds,
    args=SFTConfig(output_dir=ckpt_dir, dataset_text_field='text', packing=False, **{seq_kw: MAX_SEQ},
                   per_device_train_batch_size=1, gradient_accumulation_steps=16, num_train_epochs=cfg['epochs'],
                   learning_rate=cfg['lr'], lr_scheduler_type='cosine', warmup_steps=6, logging_steps=5,
                   save_strategy='steps', save_steps=25, save_total_limit=2, bf16=True, optim='adamw_8bit',
                   seed=cfg['seed'], report_to=report, run_name=f'sme-drhp-{RUN}'))
trainer = train_on_responses_only(trainer, instruction_part='<|im_start|>user\\n', response_part='<|im_start|>assistant\\n')
last = None
if os.path.isdir(ckpt_dir):
    ck = sorted((d for d in os.listdir(ckpt_dir) if d.startswith('checkpoint-')), key=lambda d: int(d.split('-')[1]))
    last = f'{ckpt_dir}/{ck[-1]}' if ck else None
print('rows', len(ds), '| resume from', last)
trainer.train(resume_from_checkpoint=last)
model.save_pretrained(f'{out_dir}/adapter'); tok.save_pretrained(f'{out_dir}/adapter')
json.dump({'run': RUN, **cfg, 'base': BASE, 'log': trainer.state.log_history[-5:]}, open(f'{out_dir}/train_summary.json', 'w'), indent=1)
""")
code("""
# held-out loss on the test rows, adapter on and off: the yes/no measure for a configuration (no generation, so
# decoding loops cannot distort it). Runs straight after training, or alone: Restart session, stage 0, the RUNS cell,
# then this cell (it loads runs/<RUN>/adapter). About 5 minutes.
import torch
if 'model' not in globals():
    from unsloth import FastLanguageModel
    model, tok = FastLanguageModel.from_pretrained(f'{out_dir}/adapter', max_seq_length=MAX_SEQ, load_in_4bit=True)
model.eval()
test = [json.loads(l) for l in open(f'{DRIVE}/out/test.jsonl', encoding='utf-8')]

def nll(r):
    n = len(tok(tok.apply_chat_template(r['messages'][:-1], tokenize=False, add_generation_prompt=True)).input_ids)
    ids = tok(tok.apply_chat_template(r['messages'], tokenize=False), return_tensors='pt').input_ids.cuda()
    lab = ids.clone(); lab[:, :n] = -100
    with torch.no_grad():
        return model(input_ids=ids, labels=lab).loss.item() * (ids.shape[1] - n), ids.shape[1] - n

def mean_loss(rows):
    s = [nll(r) for r in rows]
    return sum(a for a, _ in s) / sum(b for _, b in s)

res = {}
for sk in ('drafting', 'extraction'):
    rs = [r for r in test if r['metadata']['skill'] == sk]
    res[sk] = {'adapter': mean_loss(rs)}
    with model.disable_adapter():
        res[sk]['base'] = mean_loss(rs)
    print(f"{sk:10s} held-out loss  {RUN} {res[sk]['adapter']:.3f}  |  base {res[sk]['base']:.3f}  ({len(rs)} rows)")
json.dump(res, open(f'{out_dir}/heldout_loss.json', 'w'), indent=1)
""")
code("""
# predictions on the test rows (B0 = base model with no adapter; set ADAPTER=None)
# run in a fresh runtime (Restart session, stage 0, the RUNS cell, then this one): the training model would
# otherwise still hold the L4's memory when vLLM starts
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest
from transformers import AutoTokenizer
from data.prompts import trim_repeats      # needs the package from 1 Nov 2026 or later (stage 0 zip)
tok = AutoTokenizer.from_pretrained(BASE)
BASELINE = False                         # True for baseline B0 (base model, no adapter)
TEMP = 0                                 # drafting only: 0 = greedy; 0.3 = low-temperature sampling (run A loops under greedy)
ADAPTER = None if BASELINE else f'{out_dir}/adapter'
pred_dir = out_dir if ADAPTER else f'{DRIVE}/runs/B0'
tag = '' if TEMP == 0 else f'_t{TEMP:g}'.replace('.', '')    # 0.3 writes predictions_test_t03.jsonl
os.makedirs(pred_dir, exist_ok=True)
llm = LLM(BASE, enable_lora=ADAPTER is not None, max_lora_rank=64, max_model_len=MAX_SEQ, gpu_memory_utilization=0.9)
rows = [json.loads(l) for l in open(f'{DRIVE}/out/test.jsonl', encoding='utf-8')]
prompts = [tok.apply_chat_template(r['messages'][:-1], tokenize=False, add_generation_prompt=True) for r in rows]
# caps from the target lengths (99th percentile: drafting about 2,100 tokens, extraction about 2,350)
cap = {'drafting': 2200, 'extraction': 3000}
# extraction stays greedy (values are copied exactly); a fixed seed makes a sampled run repeatable
params = [SamplingParams(temperature=TEMP, top_p=0.9, seed=1234, max_tokens=cap['drafting'])
          if TEMP and r['metadata']['skill'] == 'drafting' else
          SamplingParams(temperature=0, max_tokens=cap[r['metadata']['skill']]) for r in rows]
outs = llm.generate(prompts, params, lora_request=LoRARequest('a', 1, ADAPTER) if ADAPTER else None)
n_cut = n_cap = 0
with open(f'{pred_dir}/predictions_test{tag}.jsonl', 'w', encoding='utf-8') as fh:
    for r, o in zip(rows, outs):
        raw, finish = o.outputs[0].text, o.outputs[0].finish_reason
        pred, cut = trim_repeats(raw) if r['metadata']['skill'] == 'drafting' else (raw, False)
        n_cut += cut; n_cap += finish == 'length'
        fh.write(json.dumps({'id': r['id'], 'metadata': r['metadata'], 'prediction': pred, 'raw': raw,
                             'finish': finish, 'loop_trimmed': cut}, ensure_ascii=False) + '\\n')
print(f'predictions_test{tag}.jsonl written: {len(rows)} rows, {n_cap} hit the cap, {n_cut} drafts trimmed at a loop')
""")

nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": []},
                                   "kernelspec": {"display_name": "Python 3", "name": "python3"}},
      "nbformat": 4, "nbformat_minor": 0}


def package(path):
    keep_dirs = ("data", "teacher", "mock", "draft", "extract", "rag", "serve")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for d in keep_dirs:
            for base, _dirs, files in os.walk(os.path.join(ROOT, d)):
                if "__pycache__" in base:
                    continue
                for f in files:
                    if f.endswith(".py"):
                        full = os.path.join(base, f)
                        z.write(full, os.path.relpath(full, ROOT))
        for rel in ("trainset/screen/screen_jobs.jsonl", "trainset/screen/screen_units.jsonl", "trainset/work/teacher_jobs.jsonl",
                    "trainset/work/gapfill_jobs.jsonl", "trainset/work/common_words.json", "trainset/screen/reviewer_labels.json"):
            full = os.path.join(ROOT, rel)
            if os.path.isfile(full):
                z.write(full, rel)
    return path


if __name__ == "__main__":
    nb_path = os.path.join(HERE, "sme_drhp_colab.ipynb")
    with open(nb_path, "w", encoding="utf-8") as fh:
        json.dump(nb, fh, indent=1, ensure_ascii=False)
    z = package(os.path.join(HERE, "sme_drhp_colab.zip"))
    print(f"{nb_path} ({len(cells)} cells)\n{z} ({os.path.getsize(z) // 1024} KB)")
