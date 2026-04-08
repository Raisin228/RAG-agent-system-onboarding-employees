from sentence_transformers import SentenceTransformer


model = SentenceTransformer('BAAI/bge-small-en')
# model.save('~/.cache/huggingface/BAAI-bge-small-en')

embedding = model.encode("привет")

print(len(embedding))
print('hi')
