import os
import uuid
from pathlib import Path

import docx
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

S3_ENDPOINT = os.environ["S3_ENDPOINT"]
S3_BUCKET = os.environ["S3_BUCKET"]
S3_REGION = os.environ["S3_REGION"]
S3_ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
S3_SECRET_KEY = os.environ["S3_SECRET_KEY"]

print("[СИСТЕМА] Инициализация клиента S3...")
s3_client = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    region_name=S3_REGION,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY
)
print("[СИСТЕМА] Успешное подключение к S3 хранилищу.\n")

def upload_image_to_s3(image_bytes: bytes, content_type: str) -> str:
    """Загружает картинку в S3 и возвращает публичную ссылку"""
    ext = content_type.split('/')[-1]
    filename = f"doc_images/img_{uuid.uuid4().hex[:8]}.{ext}"
    
    print(f"      [S3] Подготовка к загрузке. Размер файла: {len(image_bytes) / 1024:.1f} КБ")
    print(f"      [S3] Сгенерировано уникальное имя: {filename}")
    
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=filename,
            Body=image_bytes,
            ContentType=content_type
            # Если бакет не публичный по умолчанию, можно добавить ACL='public-read'
            # при условии, что настройки безопасности Timeweb это разрешают.
        )
        
        # Для Timeweb Cloud публичная ссылка формируется так:
        url = f"{S3_ENDPOINT}/{S3_BUCKET}/{filename}"
        print(f"      [S3] УСПЕХ! Файл загружен. Ссылка: {url}")
        return url
        
    except ClientError as e:
        print(f"      [S3 ОШИБКА] Не удалось загрузить файл: {e}")
        return ""

def parse_docx_with_images(filepath: str) -> list[str]:
    """
    Читает Word документ, извлекает текст и перехватывает бинарники картинок,
    сохраняя исходную последовательность элементов.
    """
    print(f"--- НАЧАЛО РАЗБОРА ДОКУМЕНТА: {filepath} ---\n")
    
    try:
        doc = docx.Document(filepath)
    except Exception as e:
        print(f"[ОШИБКА] Не удалось открыть файл {filepath}: {e}")
        return []

    content_blocks = []
    
    # Пространства имен XML для поиска картинок внутри структуры DOCX
    NS = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    }
    
    print(f"[*] Документ загружен. Всего абзацев для проверки: {len(doc.paragraphs)}\n")
    
    for paragraph_index, p in enumerate(doc.paragraphs):
        para_text = ""
        has_content = False
        
        # Проверяем все элементы внутри абзаца (runs)
        for run_index, run in enumerate(p.runs):
            # 1. Читаем текст
            if run.text:
                para_text += run.text
                has_content = True
                
            # 2. Ищем спрятанные изображения (теги <w:drawing>)
            drawings = run.element.findall('.//w:drawing', NS)
            for drawing in drawings:
                blips = drawing.findall('.//a:blip', NS)
                for blip in blips:
                    rId = blip.get(f"{{{NS['r']}}}embed")
                    if rId:
                        has_content = True
                        print(f"   >>> НАЙДЕНА КАРТИНКА (Абзац {paragraph_index + 1}, Блок {run_index + 1})")
                        print(f"      [ПАРСЕР] Извлекаем бинарные данные по внутреннему ID: {rId}")
                        
                        image_part = doc.part.related_parts[rId]
                        image_bytes = image_part.blob
                        content_type = image_part.content_type
                        
                        # Отправляем в облако
                        image_url = upload_image_to_s3(image_bytes, content_type)
                        
                        # Вшиваем Markdown-код
                        if image_url:
                            markdown_img = f"\n\n![Иллюстрация из документа]({image_url})\n\n"
                            para_text += markdown_img
                            print(f"      [ПАРСЕР] Картинка успешно конвертирована в Markdown-тег.")
                        else:
                            para_text += f"\n\n[Изображение недоступно]\n\n"
                            
        # Если в абзаце был хоть какой-то текст или картинка — сохраняем
        if has_content and para_text.strip():
            content_blocks.append(para_text.strip())
            
    print("\n--- РАЗБОР ДОКУМЕНТА ЗАВЕРШЕН ---")
    return content_blocks

if __name__ == "__main__":
    test_file = str(Path(__file__).parent / "test_instruction.docx")
    
    print("=====================================================")
    print(" DEMO: ГИБРИДНЫЙ ПАРСИНГ (ТЕКСТ + S3 ИЗОБРАЖЕНИЯ)")
    print("=====================================================\n")
    
    # 1. Запуск парсера
    blocks = parse_docx_with_images(test_file)
    
    if not blocks:
        print("\n[СИСТЕМА] Результат пуст. Проверьте тестовый документ.")
    else:
        print("\n=====================================================")
        print(" РЕЗУЛЬТАТ ДЛЯ ОТПРАВКИ В ВЕКТОРНУЮ БАЗУ (QDRANT)")
        print("=====================================================\n")
        print("Векторная база получит этот текст. Когда пользователь задаст вопрос,")
        print("нейросеть прочитает его и выдаст картинку прямо в чат Open WebUI:\n")
        
        for i, b in enumerate(blocks):
            print(f"[ЧАНК {i + 1}]:\n{b}")
            print("-" * 50)