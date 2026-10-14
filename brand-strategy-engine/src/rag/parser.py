import hashlib
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
from pypdf import PdfReader
from docx import Document


class DocumentParser:
    """Extracts raw text, tables, and structural metadata across document formats."""

    @classmethod
    def parse_file(cls, file_path: str) -> List[Dict[str, Any]]:
        """Parses a file and returns extracted document sections with source cryptographic hash."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_bytes = path.read_bytes()
        file_sha256 = hashlib.sha256(file_bytes).hexdigest()

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            sections = cls.parse_pdf(path)
        elif suffix in (".docx", ".doc"):
            sections = cls.parse_docx(path)
        elif suffix in (".csv", ".tsv"):
            sections = cls.parse_csv(path)
        elif suffix in (".xlsx", ".xls"):
            sections = cls.parse_excel(path)
        else:
            # Fallback text parser (txt, md, json, etc.)
            sections = cls.parse_text(path)

        for s in sections:
            s["sha256_hash"] = file_sha256
        return sections

    @classmethod
    def parse_pdf(cls, path: Path) -> List[Dict[str, Any]]:
        """Extracts text, tables, and page layout from PDF documents using pdfplumber / pypdf."""
        try:
            import pdfplumber  # type: ignore
            sections: List[Dict[str, Any]] = []
            with pdfplumber.open(str(path)) as pdf:
                for idx, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    tables = page.extract_tables() or []
                    table_texts = []
                    for t in tables:
                        rows = [" | ".join(str(cell or "").strip() for cell in row) for row in t if row]
                        if rows:
                            table_texts.append("\n".join(rows))
                    full_content = text.strip()
                    if table_texts:
                        full_content += "\n\nTables:\n" + "\n\n".join(table_texts)
                    if full_content.strip():
                        sections.append({
                            "source_filename": path.name,
                            "page_number": idx + 1,
                            "section_heading": f"Page {idx + 1}",
                            "content": full_content.strip(),
                        })
            if sections:
                return sections
        except Exception:
            pass

        # Standard pypdf extraction
        reader = PdfReader(str(path))
        sections = []
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
        """Extracts text, heading hierarchies, and tables from DOCX documents."""
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

        # Extract DOCX tables
        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    table_rows.append(" | ".join(cells))
            if table_rows:
                current_text.append("\nTable:\n" + "\n".join(table_rows))

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
    def parse_excel(cls, path: Path) -> List[Dict[str, Any]]:
        """Parses Excel (XLSX/XLS) spreadsheets into structured tabular sections."""
        try:
            excel_file = pd.ExcelFile(str(path))
            sections: List[Dict[str, Any]] = []
            for sheet_idx, sheet_name in enumerate(excel_file.sheet_names):
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                if df.empty:
                    continue
                schema_summary = f"Sheet: {sheet_name}. Columns: {', '.join(df.columns.astype(str))}. Total rows: {len(df)}."
                sections.append({
                    "source_filename": path.name,
                    "page_number": sheet_idx + 1,
                    "section_heading": f"Sheet: {sheet_name}",
                    "content": f"{schema_summary}\n\n{df.head(50).to_string(index=False)}",
                })
            if sections:
                return sections
        except Exception:
            pass

        return cls.parse_text(path)

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
