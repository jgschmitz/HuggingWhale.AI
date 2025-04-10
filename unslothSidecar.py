from unsloth import FastTrainer
from transformers import AutoTokenizer
from datasets import load_dataset

# Load your dataset (from MongoDB or files)
dataset = load_dataset("json", data_files="path_to_your_chunked_data.json")

# Tokenizer + model (Unsloth patching this under the hood)
tokenizer = AutoTokenizer.from_pretrained("unsloth/llama-3-8b-Instruct")
trainer = FastTrainer(
    model="unsloth/llama-3-8b-Instruct",
    tokenizer=tokenizer,
    dataset=dataset["train"],
    output_dir="./narwal_checkpoints",
    batch_size=8,
    fp16=True,
)

trainer.train()
