from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List
from PIL import Image

@dataclass
class ParsedContent:
    text: str
    images: List[Image.Image]
    metadata: dict
    source_name: str

class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> ParsedContent:
        pass
