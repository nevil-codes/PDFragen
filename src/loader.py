from pypdf import PdfReader

def load_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    pages=[]
    for page_number, page in enumerate(reader.pages,start=1):
        content = page.extract_text() or ""
        pages.append((page_number, content))
    return pages

result = load_pdf("raw/a-grammatik.pdf")
print(result[0])