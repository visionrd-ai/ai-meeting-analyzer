from huggingface_hub import snapshot_download
local_path = snapshot_download(
    repo_id="sentence-transformers/all-MiniLM-L6-v2",
    token=None  # or your new token
)
print(local_path)  # e.g., C:\Users\talal\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2