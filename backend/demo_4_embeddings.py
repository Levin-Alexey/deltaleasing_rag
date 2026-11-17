import os
import math
import requests
from dotenv import load_dotenv

# Загружаем ключи из нашего файла .env
load_dotenv("/root/deltaleasing_rag/backend/.env")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

def get_embedding(text: str) -> list[float]:
    """Отправляет текст в нейросеть и получает обратно вектор (массив чисел)"""
    response = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "openai/text-embedding-3-small", 
            "input": text
        }
    )
    # Если OpenRouter ругается, выводим ошибку
    response.raise_for_status() 
    
    # Возвращаем сам массив чисел
    return response.json()["data"][0]["embedding"]

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Вычисляет косинусное сходство между двумя векторами (в процентах от 0 до 100)"""
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    # Умножаем на 100 для наглядности (в виде процентов)
    return (dot_product / (magnitude1 * magnitude2)) * 100

def run_demo():
    print("\n--- ДЕМОНСТРАЦИЯ: КАК НЕЙРОСЕТЬ ПОНИМАЕТ СМЫСЛ ---")
    
    # 1. Задаем тестовые фразы
    text_1 = "Договор лизинга на гусеничный экскаватор"
    text_2 = "Аренда строительной спецтехники для юрлиц" # Смысл тот же, слова другие
    text_3 = "Рецепт сладкого яблочного пирога"           # Смысл совершенно другой
    
    print("\n1. Отправляем тексты в модель (text-embedding-3-small)...")
    vec_1 = get_embedding(text_1)
    vec_2 = get_embedding(text_2)
    vec_3 = get_embedding(text_3)
    
    print(f"\n2. Как выглядит вектор для фразы '{text_1}'?")
    print(f"   Размерность: {len(vec_1)} измерений (чисел).")
    print(f"   Начало вектора: {vec_1[:5]} ... (и еще {len(vec_1)-5} чисел)")
    
    print("\n3. Сравниваем смысловую близость (Косинусное расстояние):")
    
    # Сравниваем лизинг и спецтехнику
    sim_1_2 = cosine_similarity(vec_1, vec_2)
    print(f"   [ТЕСТ 1]: '{text_1}' \n         vs  '{text_2}'")
    print(f"   Сходство: {sim_1_2:.1f}%  <-- (Слова разные, но смысл ОЧЕНЬ близок!)\n")
    
    # Сравниваем лизинг и пирог
    sim_1_3 = cosine_similarity(vec_1, vec_3)
    print(f"   [ТЕСТ 2]: '{text_1}' \n         vs  '{text_3}'")
    print(f"   Сходство: {sim_1_3:.1f}%  <-- (Смысл абсолютно разный, векторы далеко друг от друга)")

if __name__ == "__main__":
    run_demo()