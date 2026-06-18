import pypdf
from PIL import Image
import io
from pathlib import Path
from src.parsers.base import BaseParser, ParsedContent
from src.utils.helpers import logger, clean_text

class PDFParser(BaseParser):
    def parse(self, file_path: str) -> ParsedContent:
        text_parts = []
        images = []
        metadata = {}
        try:
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                metadata = dict(reader.metadata or {})
                metadata['page_count'] = len(reader.pages)
                for page_num, page in enumerate(reader.pages):
                    txt = page.extract_text()
                    if txt:
                        text_parts.append(f"--- PAGE {page_num+1} ---\n{txt}")
                    if hasattr(page, 'images'):
                        for img_obj in page.images:
                            try:
                                pil_img = Image.open(io.BytesIO(img_obj.data))
                                if pil_img.mode != 'RGB':
                                    pil_img = pil_img.convert('RGB')
                                if pil_img.width > 50 and pil_img.height > 50:
                                    images.append(pil_img)
                            except Exception:
                                pass
        except Exception as e:
            logger.error(f"PDF Parse Error [{file_path}]: {e}")
            raise
        full_text = clean_text("\n".join(text_parts))
        return ParsedContent(text=full_text, images=images, metadata=metadata, source_name=Path(file_path).name)
