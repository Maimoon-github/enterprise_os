"""Multi-format document extractor for PDF, DOCX, and CSV files."""

from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
from pypdf import PdfReader
from docx import Document


class DocumentParser:
    """Extracts raw text and structural metadata across document formats."""

    @classmethod
    def parse_file(cls, file_path: str) -> List[Dict[str, Any]]:
        """Parses a file and returns extracted document sections."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return cls.parse_pdf(path)
        elif suffix in (".docx", ".doc"):
            return cls.parse_docx(path)
        elif suffix in (".csv", ".tsv"):
            return cls.parse_csv(path)
        else:
            # Fallback text parser (txt, md, json, etc.)
            return cls.parse_text(path)

    @classmethod
    def parse_pdf(cls, path: Path) -> List[Dict[str, Any]]:
        """Extracts text and page layout from PDF documents."""
        reader = PdfReader(str(path))
        sections: List[Dict[str, Any]] = []

        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                sections.append({
                    "source_filename": path.name,
                    "page_number": idx + 1,
                    "section_heading": f"Page {idx + 1}",
                    "content": text.strip(),
                })
        return sections

    @classmethod
    def parse_docx(cls, path: Path) -> List[Dict[str, Any]]:
        """Extracts text and heading hierarchies from DOCX documents."""
        doc = Document(str(path))
        sections: List[Dict[str, Any]] = []
        current_heading = "Document Overview"
        current_text: List[str] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            if para.style and para.style.name and para.style.name.startswith("Heading"):
                if current_text:
                    sections.append({
                        "source_filename": path.name,
                        "page_number": 1,
                        "section_heading": current_heading,
                        "content": "\n".join(current_text),
                    })
                    current_text = []
                current_heading = text
            else:
                current_text.append(text)

        if current_text:
            sections.append({
                "source_filename": path.name,
                "page_number": 1,
                "section_heading": current_heading,
                "content": "\n".join(current_text),
            })

        return sections

    @classmethod
    def parse_csv(cls, path: Path) -> List[Dict[str, Any]]:
        """Parses CSV datasets into structured row summaries."""
        df = pd.read_csv(str(path))
        sections: List[Dict[str, Any]] = []

        # Represent columns and high level schema
        schema_summary = f"Columns: {', '.join(df.columns.astype(str))}. Total rows: {len(df)}."
        sections.append({
            "source_filename": path.name,
            "page_number": 1,
            "section_heading": "CSV Metadata & Summary",
            "content": schema_summary,
        })

        # Process in batches of 25 rows
        batch_size = 25
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i : i + batch_size]
            batch_text = batch.to_string(index=False)
            sections.append({
                "source_filename": path.name,
                "page_number": (i // batch_size) + 1,
                "section_heading": f"Data Rows {i + 1} - {min(i + batch_size, len(df))}",
                "content": batch_text,
            })

        return sections

    @classmethod
    def parse_text(cls, path: Path) -> List[Dict[str, Any]]:
        """Reads plain text and markdown files."""
        content = path.read_text(encoding="utf-8", errors="replace")
        return [{
            "source_filename": path.name,
            "page_number": 1,
            "section_heading": "Document Content",
            "content": content.strip(),
        }]
