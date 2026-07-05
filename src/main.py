from loader import load_pdf
from chunker import chunk_text

pages = load_pdf("raw/a-grammatik.pdf")
chunks = list(chunk_text(pages, chunk_size=500, overlap=20))
print(len(chunks))
print(len(chunks[7][1]))