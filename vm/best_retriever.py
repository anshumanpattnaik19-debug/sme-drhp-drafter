"""Print the retriever of vm/retrieval_eval.py with the best recall@5 (ties: MRR@10), as its contexts file stem."""
import json
import sys

m = json.load(open(sys.argv[1]))["methods"]
print(max(m, key=lambda k: (m[k]["recall@5"], m[k]["mrr@10"])).replace("+", "_"))
