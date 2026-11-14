import os, uuid, hashlib, requests, psycopg2, time
from psycopg2.extras import Json
from dotenv import load_dotenv
import docx
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
import pdfplumber
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, PayloadSchemaType

load_dotenv("/root/deltaleasing_rag/backend/.env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "1536"))
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "deltaleasing_kb")
DOCS_BASE_DIR = os.getenv("DOCS_BASE_DIR", "/root/deltaleasing_rag/docs")

FOLDER_ROLES = {
    "general": ["user", "sales", "security", "admin"],
    "sales": ["sales", "admin"],
    "security": ["security", "admin"],
    "admin": ["admin"],
}

qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASS")
    )

def init_qdrant():
    if not qdrant.collection_exists(COLLECTION_NAME):
        qdrant.create_collection(collection_name=COLLECTION_NAME, vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE))
        qdrant.create_payload_index(collection_name=COLLECTION_NAME, field_name="access_roles", field_schema=PayloadSchemaType.KEYWORD)
        qdrant.create_payload_index(collection_name=COLLECTION_NAME, field_name="doc_id", field_schema=PayloadSchemaType.KEYWORD)
        print(f"[INIT] Коллекция '{COLLECTION_NAME}' и индексы созданы.")

def table_to_markdown_docx(table: Table) -> str:
    md_rows = []
    for i, row in enumerate(table.rows):
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        md_rows.append("| " + " | ".join(cells) + " |")
        if i == 0: md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return "\n".join(md_rows)

def parse_docx_to_chunks(file_path: str, max_chunk_chars: int = 1200) -> list[str]:
    doc = docx.Document(file_path)
    blocks = []
    for child in doc.element.body:
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            if p.text.strip(): blocks.append(p.text.strip())
        elif isinstance(child, CT_Tbl):
            t = Table(child, doc)
            blocks.append(table_to_markdown_docx(t))
    return _pack_blocks_to_chunks(blocks, max_chunk_chars)

def parse_pdf_to_chunks(file_path: str, max_chunk_chars: int = 1200) -> list[str]:
    blocks = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table: continue
                md_rows = []
                for i, row in enumerate(table):
                    cells = [(c or "").strip().replace("\n", " ") for c in row]
                    md_rows.append("| " + " | ".join(cells) + " |")
                    if i == 0: md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
                blocks.append("\n".join(md_rows))
            text = page.extract_text()
            if text and text.strip(): blocks.append(text.strip())
    return _pack_blocks_to_chunks(blocks, max_chunk_chars)

def _pack_blocks_to_chunks(blocks: list[str], max_chars: int) -> list[str]:
    chunks = []
    current_chunk = ""
    for block in blocks:
        if len(current_chunk) + len(block) + 2 <= max_chars:
            current_chunk = (current_chunk + "\n\n" + block).strip()
        else:
            if current_chunk: chunks.append(current_chunk)
            current_chunk = block
    if current_chunk: chunks.append(current_chunk)
    return chunks

def get_embeddings(texts: list[str]) -> list[list[float]]:
    response = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        json={"model": EMBEDDING_MODEL, "input": texts}, timeout=60
    )
    response.raise_for_status()
    data = response.json()["data"]
    data.sort(key=lambda x: x["index"])
    return [item["embedding"] for item in data]

def get_file_hash(filepath: str) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f: hasher.update(f.read())
    return hasher.hexdigest()

def delete_from_qdrant(doc_id: str):
    qdrant.delete(collection_name=COLLECTION_NAME, points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]))

def sync():
    init_qdrant()
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT doc_id, file_hash FROM document_registry;")
    db_state = {row[0]: row[1] for row in cur.fetchall()}

    disk_files = {}
    for folder, roles in FOLDER_ROLES.items():
        folder_path = os.path.join(DOCS_BASE_DIR, folder)
        os.makedirs(folder_path, exist_ok=True)
        for fname in os.listdir(folder_path):
            fname_lower = fname.lower()
            if not (fname_lower.endswith(".docx") or fname_lower.endswith(".pdf")): continue
            if fname.startswith("~$") or fname.startswith("."): continue
            
            full_path = os.path.join(folder_path, fname)
            doc_id = f"{folder}/{fname}"
            disk_files[doc_id] = {
                "path": full_path, "hash": get_file_hash(full_path),
                "roles": roles, "fname": fname,
                "ext": ".pdf" if fname_lower.endswith(".pdf") else ".docx"
            }

    for old_doc_id in list(db_state.keys()):
        if old_doc_id not in disk_files:
            print(f"[УДАЛЕНИЕ] {old_doc_id} исчез с диска. Удаляем из Qdrant...")
            delete_from_qdrant(old_doc_id)
            cur.execute("DELETE FROM document_registry WHERE doc_id = %s;", (old_doc_id,))

    for doc_id, info in disk_files.items():
        old_hash = db_state.get(doc_id)
        if old_hash == info["hash"]: continue

        if old_hash is not None:
            print(f"[ОБНОВЛЕНИЕ] {doc_id} изменён. Переиндексация...")
            delete_from_qdrant(doc_id)
        else:
            print(f"[НОВЫЙ] Индексация {doc_id}...")

        try:
            chunks = parse_pdf_to_chunks(info["path"]) if info["ext"] == ".pdf" else parse_docx_to_chunks(info["path"])
        except Exception as e:
            print(f"[ОШИБКА] Не удалось распарсить {doc_id}: {e}")
            continue

        if not chunks:
            print(f"[ПРОПУСК] Файл {doc_id} пуст.")
            continue

        vectors = get_embeddings(chunks)
        points = [
            PointStruct(id=str(uuid.uuid4()), vector=vec, payload={"text": chunk, "doc_id": doc_id, "source": info["fname"], "access_roles": info["roles"]})
            for chunk, vec in zip(chunks, vectors)
        ]
        qdrant.upsert(collection_name=COLLECTION_NAME, points=points)

        cur.execute(
            """INSERT INTO document_registry (doc_id, file_path, file_hash, access_roles, chunks_count, updated_at) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (doc_id) DO UPDATE SET file_hash = EXCLUDED.file_hash, access_roles = EXCLUDED.access_roles, chunks_count = EXCLUDED.chunks_count, updated_at = CURRENT_TIMESTAMP;""",
            (doc_id, info["path"], info["hash"], Json(info["roles"]), len(points)),
        )
        print(f"[ГОТОВО] {doc_id} -> загружено чанков: {len(points)}")

    conn.commit()
    cur.close()
    conn.close()
    print("Синхронизация завершена. Ожидание изменений...")

if __name__ == "__main__":
    print("Запуск фонового сервиса синхронизации (интервал: 15 минут)...")
    while True:
        try:
            sync()
        except Exception as e:
            print(f"[КРИТИЧЕСКАЯ ОШИБКА] {e}")
        time.sleep(900)
