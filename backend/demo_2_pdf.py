from pathlib import Path

import pdfplumber

def demo_pdf_parsing(filepath):
    print(f"\n--- 2. ЧТЕНИЕ PDF ДОКУМЕНТА ({filepath}) ---")
    
    # Открываем PDF файл
    with pdfplumber.open(filepath) as pdf:
        print(f"Всего страниц в документе: {len(pdf.pages)}\n")
        
        # Идем постранично
        for i, page in enumerate(pdf.pages):
            print(f"=== СТРАНИЦА {i + 1} ===")
            
            # Извлекаем весь текст со страницы (pdfplumber сам пытается угадать порядок)
            text = page.extract_text()
            
            if text:
                print(text)
            else:
                print("[Страница пуста или это картинка без текстового слоя]")
            
            print("=" * 20 + "\n")

if __name__ == "__main__":
    try:
        demo_pdf_parsing(Path(__file__).parent / "test_doc.pdf")
    except Exception as e:
        print(f"Ошибка (файл test_doc.pdf существует?): {e}")