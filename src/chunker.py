
def chunk_text(pages, chunk_size, overlap):
    for page_number, text in pages:
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]
            yield (page_number, chunk)
            start += chunk_size - overlap