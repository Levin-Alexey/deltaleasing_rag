import docx
from pathlib import Path

def demo_docx_parsing(filepath):
    print(f"\n--- 1. ЧТЕНИЕ WORD ДОКУМЕНТА ({filepath}) ---")
    
    # Загружаем документ
    doc = docx.Document(filepath)
    
    # Идем по абзацам (paragraphs)
    for i, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        
        # Пропускаем пустые абзацы
        if text:
            print(f"[Абзац {i + 1}]: {text}")
            print("-" * 20)

if __name__ == "__main__":
    try:
        demo_docx_parsing(Path(__file__).parent / "test_doc.docx")
    except Exception as e:
        print(f"Ошибка (файл test_doc.docx существует?): {e}")