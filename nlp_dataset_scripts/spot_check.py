import json, random
random.seed(7)

with open(r'C:\Users\anany\OneDrive\Desktop\majorproject\retail-automation-project-main\Retail_NLP_Training_Dataset.jsonl', encoding='utf-8') as f:
    samples = [json.loads(l) for l in f]

print(f"Total samples: {len(samples)}")
print()

# Sample 2349 (the flagged ambiguous one)
s = samples[2349]
print("=== Sample 2349 (flagged for review) ===")
print("Text:", s["text"])
for st, en, lbl in s["entities"]:
    print(f"  {lbl}: [{st},{en}] -> '{s['text'][st:en]}'")
print()

# 10 random samples
print("=== 10 random samples ===")
for idx in random.sample(range(3000), 10):
    s = samples[idx]
    print(f"[{idx}] {s['text']}")
    for st, en, lbl in s["entities"]:
        print(f"  {lbl}: [{st},{en}] -> '{s['text'][st:en]}'")
    print()
