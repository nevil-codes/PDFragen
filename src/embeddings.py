from sentence_transformers import SentenceTransformer
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
def embed_chunk(chunk):
    return model.encode(chunk)