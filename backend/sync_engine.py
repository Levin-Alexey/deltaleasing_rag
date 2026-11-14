import os
from pathlib import Path

import requests
import psycopg2
from dotenv import load_dotenv
from typing import Callable, Any

load_dotenv(Path(__file__).resolve().with_name(".env"))


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


class Tools:
    def __init__(self):
        self.QDRANT_URL = _required_env("QDRANT_URL")
        self.QDRANT_API_KEY = _required_env("QDRANT_API_KEY")
        self.OPENROUTER_API_KEY = _required_env("OPENROUTER_API_KEY")
        self.COLLECTION = _required_env("COLLECTION_NAME")
        self.EMBEDDING_MODEL = _required_env("EMBEDDING_MODEL")
        
        # Реквизиты локальной базы данных
        self.DB_HOST = _required_env("DB_HOST")
        self.DB_PORT = _required_env("DB_PORT")
        self.DB_NAME = _required_env("DB_NAME")
        self.DB_USER = _required_env("DB_USER")
        self.DB_PASS = _required_env("DB_PASS")

    def _get_user_role(self, email: str) -> str:
        """Получает роль пользователя из базы данных PostgreSQL"""
        if not email:
            return "user"
        try:
            conn = psycopg2.connect(
                host=self.DB_HOST, port=self.DB_PORT,
                dbname=self.DB_NAME, user=self.DB_USER, password=self.DB_PASS
            )
            cur = conn.cursor()
            cur.execute("SELECT corporate_role FROM user_roles WHERE email = %s;", (email,))
            result = cur.fetchone()
            cur.close()
            conn.close()
            return result[0] if result else "user"
        except Exception as e:
            print(f"Ошибка БД: {e}")
            return "user"

    def search_corporate_documents(self, query: str, __user__: dict) -> str:
        """
        Искать регламенты, ставки и правила в корпоративной базе знаний Дельтализинг.
        Вызывай этот инструмент ВСЕГДА, когда пользователь спрашивает о лизинге, тарифах или документах.
        """
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # 1. Берем email из интерфейса и динамически узнаем роль из Postgres
        user_email = __user__.get("email", "")
        user_role = self._get_user_role(user_email)

        try:
            # 2. Получаем вектор вопроса
            resp = requests.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={"Authorization": f"Bearer {self.OPENROUTER_API_KEY}"},
                json={"model": self.EMBEDDING_MODEL, "input": query},
                timeout=15
            )
            resp.raise_for_status()
            query_vector = resp.json()["data"][0]["embedding"]

            # 3. Идем в Qdrant с фильтром по полученной роли (RBAC)
            client = QdrantClient(url=self.QDRANT_URL, api_key=self.QDRANT_API_KEY)
            
            rbac_filter = Filter(
                must=[FieldCondition(key="access_roles", match=MatchValue(value=user_role))]
            )

            results = client.search(
                collection_name=self.COLLECTION,
                query_vector=query_vector,
                query_filter=rbac_filter,
                limit=4
            )

            if not results:
                return f"[СИСТЕМА] В базе знаний для роли '{user_role}' ({user_email}) ничего не найдено. Сообщи об этом."

            # 4. Формируем контекст
            context = f"--- НАЙДЕННЫЕ ДОКУМЕНТЫ (РОЛЬ: {user_role}) ---\n\n"
            for r in results:
                source = r.payload.get("source", "Неизвестный файл")
                text = r.payload.get("text", "")
                context += f"📜 Источник: {source}\n{text}\n\n"

            return context

        except Exception as e:
            return f"Ошибка поиска: {str(e)}"