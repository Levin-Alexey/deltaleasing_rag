from pathlib import Path

import pandas as pd

def excel_to_markdown(filepath: str) -> str:
    """Читает Excel файл и превращает его в идеальный Markdown для нейросети"""
    print(f"\n--- 3. УМНЫЙ ПАРСИНГ EXCEL ({filepath}) ---")
    
    try:
        # Читаем первую страницу Excel-файла
        # dtype=str гарантирует, что мы не потеряем нули в начале номеров договоров (например, 00123)
        df = pd.read_excel(filepath, dtype=str)
        
        # Заменяем пустые ячейки (NaN) на пустые строки, чтобы не было мусора
        df = df.fillna("")
        
        md_rows = []
        
        # 1. Достаем заголовки колонок (первая строка таблицы)
        headers = [str(col).strip().replace("\n", " ") for col in df.columns]
        md_rows.append("| " + " | ".join(headers) + " |")
        
        # 2. Добавляем разделительную линию Markdown
        md_rows.append("| " + " | ".join(["---"] * len(headers)) + " |")
        
        # 3. Идем по всем остальным строкам
        for _, row in df.iterrows():
            cells = [str(cell).strip().replace("\n", " ") for cell in row.values]
            md_rows.append("| " + " | ".join(cells) + " |")
            
        markdown_result = "\n".join(md_rows)
        
        print("\n[КАК ЭТО ВИДИТ НЕЙРОСЕТЬ (Формат Markdown)]:\n")
        print(markdown_result)
        
        return markdown_result

    except Exception as e:
        print(f"Ошибка чтения Excel: {e}")

if __name__ == "__main__":
    # Убедитесь, что файл test_table.xlsx лежит в этой же папке!
    excel_to_markdown(str(Path(__file__).parent / "test_table.xlsx"))