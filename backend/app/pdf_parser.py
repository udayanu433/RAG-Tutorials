import pdfplumber
import re

def parse_pdf_structured(pdf_path: str) -> str:
    """
    Parses a PDF file using pdfplumber, extracting both text and tables.
    Tables are converted to markdown format and appended to each page's text
    to preserve their structural layout for the RAG LLM.
    """
    structured_content = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            
            # Extract tables from the page
            tables = page.extract_tables()
            table_markdown_blocks = []
            
            for table in tables:
                if not table or not any(table):
                    continue
                    
                # Clean table cells (remove extra spaces and handle None values)
                cleaned_rows = []
                for row in table:
                    if not row:
                        continue
                    cleaned_row = [str(cell or "").replace("\n", " ").strip() for cell in row]
                    cleaned_rows.append(cleaned_row)
                
                if not cleaned_rows:
                    continue
                
                # Reconstruct table as Markdown
                header = cleaned_rows[0]
                # Avoid empty headers by giving dummy titles if needed
                header = [col if col else f"Column {idx+1}" for idx, col in enumerate(header)]
                
                markdown_table = "| " + " | ".join(header) + " |\n"
                markdown_table += "| " + " | ".join(["---"] * len(header)) + " |\n"
                
                for row in cleaned_rows[1:]:
                    # Match column counts
                    if len(row) < len(header):
                        row += [""] * (len(header) - len(row))
                    elif len(row) > len(header):
                        row = row[:len(header)]
                    markdown_table += "| " + " | ".join(row) + " |\n"
                
                table_markdown_blocks.append(markdown_table)
            
            # Assemble page contents
            combined_page_content = f"--- Page {i+1} ---\n{page_text}"
            if table_markdown_blocks:
                combined_page_content += "\n\n### Extracted Structured Table Data:\n" + "\n\n".join(table_markdown_blocks)
            
            structured_content.append(combined_page_content)
            
    return "\n\n".join(structured_content)

def parse_pdf_structured_pages(pdf_path: str) -> list:
    """
    Parses a PDF file page-by-page, returning a list of dictionaries.
    Each entry contains the 'page_number' and the 'content' (combining text and tables in Markdown format).
    """
    pages_data = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            
            # Extract tables from the page
            tables = page.extract_tables()
            table_markdown_blocks = []
            
            for table in tables:
                if not table or not any(table):
                    continue
                    
                # Clean table cells
                cleaned_rows = []
                for row in table:
                    if not row:
                        continue
                    cleaned_row = [str(cell or "").replace("\n", " ").strip() for cell in row]
                    cleaned_rows.append(cleaned_row)
                
                if not cleaned_rows:
                    continue
                
                # Reconstruct table as Markdown
                header = cleaned_rows[0]
                header = [col if col else f"Column {idx+1}" for idx, col in enumerate(header)]
                
                markdown_table = "| " + " | ".join(header) + " |\n"
                markdown_table += "| " + " | ".join(["---"] * len(header)) + " |\n"
                
                for row in cleaned_rows[1:]:
                    if len(row) < len(header):
                        row += [""] * (len(header) - len(row))
                    elif len(row) > len(header):
                        row = row[:len(header)]
                    markdown_table += "| " + " | ".join(row) + " |\n"
                
                table_markdown_blocks.append(markdown_table)
            
            # Assemble page contents
            combined_page_content = f"--- Page {i+1} ---\n{page_text}"
            if table_markdown_blocks:
                combined_page_content += "\n\n### Extracted Structured Table Data:\n" + "\n\n".join(table_markdown_blocks)
            
            pages_data.append({
                "page_number": i + 1,
                "content": combined_page_content
            })
            
    return pages_data

if __name__ == "__main__":
    # Test script if called directly
    import sys
    if len(sys.argv) > 1:
        pages = parse_pdf_structured_pages(sys.argv[1])
        for p in pages:
            print(f"PAGE {p['page_number']}:\n{p['content'][:200]}...\n")
