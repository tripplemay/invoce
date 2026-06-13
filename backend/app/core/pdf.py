"""PDF 首页渲染为 PNG（送多模态模型前的预处理）。"""

import fitz  # PyMuPDF


def pdf_first_page_png(pdf_bytes: bytes) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)
        return pix.tobytes("png")
    finally:
        doc.close()
