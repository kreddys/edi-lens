# FILE: backend/src/agents/refinement_engine/document_loader.py
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from llama_index.core import Document
import pypdf

from .models import KnowledgeSource

logger = logging.getLogger(__name__)

class DocumentLoader(ABC):
    """Abstract base class for all document loaders."""
    @abstractmethod
    def load(self) -> List[Document]:
        """Loads a knowledge source and returns a list of LlamaIndex Documents."""
        pass

# --- NEW, ROBUST LOADER ---
class SectionLoader(DocumentLoader):
    """
    Loads a text file and splits it into multiple Document objects based on
    a specified separator. This is ideal for pre-chunking structured text.
    """
    def __init__(self, file_path: Path, separator: str = "\n\n---\n\n"):
        self.file_path = file_path
        self.separator = separator
        
    def load(self) -> List[Document]:
        try:
            full_content = self.file_path.read_text()
            sections = full_content.split(self.separator)
            
            documents = []
            for i, section_text in enumerate(sections):
                if section_text.strip(): # Ensure we don't create empty documents
                    doc = Document(
                        text=section_text, 
                        # Add metadata to each document for traceability
                        metadata={"section": i + 1, "file_name": self.file_path.name}
                    )
                    documents.append(doc)
            
            logger.info(f"Successfully loaded and split '{self.file_path.name}' into {len(documents)} sections.")
            return documents
        except Exception as e:
            logger.error(f"Failed to read or split file {self.file_path}: {e}", exc_info=True)
            return []

# --- EXISTING LOADERS (NO CHANGE) ---
class PdfLoader(DocumentLoader):
    """Loads a PDF file and extracts its text content."""
    def __init__(self, file_path: Path):
        self.file_path = file_path

    def load(self) -> List[Document]:
        text_content = ""
        try:
            with open(self.file_path, "rb") as f:
                pdf_reader = pypdf.PdfReader(f)
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"
            logger.info(f"Successfully extracted text from PDF: {self.file_path}")
            return [Document(text=text_content, doc_id=str(self.file_path))]
        except Exception as e:
            logger.error(f"Failed to read PDF file {self.file_path}: {e}", exc_info=True)
            return []

class TextFileLoader(DocumentLoader):
    """Loads a plain text file as a single Document."""
    def __init__(self, file_path: Path):
        self.file_path = file_path

    def load(self) -> List[Document]:
        try:
            text_content = self.file_path.read_text()
            logger.info(f"Successfully loaded text file: {self.file_path}")
            return [Document(text=text_content, doc_id=str(self.file_path))]
        except Exception as e:
            logger.error(f"Failed to read text file {self.file_path}: {e}", exc_info=True)
            return []

class RawTextLoader(DocumentLoader):
    """'Loads' raw text directly into a Document."""
    def __init__(self, text: str, doc_id: str = "raw_text_input"):
        self.text = text
        self.doc_id = doc_id

    def load(self) -> List[Document]:
        logger.info(f"Loading raw text input with id: '{self.doc_id}'")
        return [Document(text=self.text, doc_id=self.doc_id)]

# --- UPDATED FACTORY FUNCTION ---
def get_loader(knowledge_source: KnowledgeSource) -> DocumentLoader:
    """
    Factory function that returns the appropriate document loader
    based on the knowledge source type and content.
    """
    source_type = knowledge_source.source_type
    content = knowledge_source.content

    if source_type == "text":
        return RawTextLoader(text=content)
    
    # --- THIS IS THE KEY CHANGE ---
    # We now look for a more specific source type to use our new loader.
    if source_type == "file_sections":
        return SectionLoader(file_path=Path(content))
    # --- END OF CHANGE ---

    if source_type == "file":
        file_path = Path(content)
        if not file_path.is_file():
            raise FileNotFoundError(f"The specified file does not exist: {file_path}")
        
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            return PdfLoader(file_path=file_path)
        if suffix == ".txt":
            # Default behavior for a .txt file is still to load it whole.
            return TextFileLoader(file_path=file_path)
        
        raise NotImplementedError(f"File type '{suffix}' is not supported.")

    raise ValueError(f"Unknown knowledge source type: '{source_type}'")