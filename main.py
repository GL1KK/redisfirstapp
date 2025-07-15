from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager
from redis.asyncio import Redis, ConnectionPool
from dotenv import load_dotenv
import os
import asyncio
import random
import json
from datetime import timedelta
from typing import Optional
from pydantic import BaseModel

load_dotenv()

# Модели данных для документации
class RandomNumberResponse(BaseModel):
    """Модель ответа для случайного числа"""
    data: dict
    source: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "data": {"number": 42},
                "source": "generated"
            }
        }

class RandomUserResponse(BaseModel):
    """Модель ответа для случайного пользователя"""
    data: dict
    source: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "data": {
                    "id": 1234,
                    "name": "Иван Петров",
                    "age": 30,
                    "email": "user123@example.com"
                },
                "source": "cache"
            }
        }

class RedisClient:
    """Клиент для работы с Redis (пул соединений)"""
    _pool: Optional[ConnectionPool] = None

    @classmethod
    async def get_redis(cls) -> Redis:
        """Получение Redis соединения из пула"""
        if cls._pool is None:
            cls._pool = ConnectionPool.from_url(
                f"redis://{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}",
                password=os.getenv("REDIS_PASSWORD") or None,
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,
                max_connections=20
            )
        return Redis(connection_pool=cls._pool)

    @classmethod
    async def close(cls):
        """Закрытие всех соединений Redis"""
        if cls._pool:
            await cls._pool.disconnect()
            cls._pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекст жизненного цикла приложения:
    - Инициализация Redis при старте
    - Очистка соединений при завершении
    """
    await RedisClient.get_redis()
    yield
    await RedisClient.close()

app = FastAPI(
    lifespan=lifespan,
    title="Random Data Generator API",
    description="API для генерации случайных данных с кешированием в Redis",
    version="1.0.0",
    contact={
        "name": "Поддержка",
        "email": "support@example.com"
    },
    license_info={
        "name": "MIT",
    },
)

async def get_cached_data(key: str) -> Optional[str]:
    """
    Получение данных из кеша Redis
    
    Args:
        key: Ключ для поиска в кеше
        
    Returns:
        Значение из кеша или None, если ключ не найден
    """
    redis = await RedisClient.get_redis()
    return await redis.get(key)

async def set_cached_data(key: str, value: str, expire_seconds: int = 60) -> None:
    """
    Сохранение данных в кеш Redis с TTL
    
    Args:
        key: Ключ для сохранения
        value: Значение для кеширования
        expire_seconds: Время жизни записи в секундах (по умолчанию 60)
    """
    redis = await RedisClient.get_redis()
    await redis.setex(key, expire_seconds, value)

@app.get(
    "/random-number",
    response_model=RandomNumberResponse,
    summary="Получить случайное число",
    description="""Генерирует случайное число от 1 до 100 с имитацией задержки сервера.
    Результат кешируется на 30 секунд.""",
    tags=["Генератор чисел"]
)
async def get_random_number():
    """
    Генерация случайного числа:
    
    - Проверяет кеш Redis
    - Если нет в кеше, генерирует новое число с задержкой 0.5-2 сек
    - Сохраняет результат в кеш на 30 секунд
    
    Returns:
        Словарь с числом и источником данных (cache/generated)
    """
    cache_key = "random_number"
    
    cached = await get_cached_data(cache_key)
    if cached:
        return {"data": json.loads(cached), "source": "cache"}
    
    await asyncio.sleep(random.uniform(0.5, 2.0))
    data = {"number": random.randint(1, 100)}
    await set_cached_data(cache_key, json.dumps(data), expire_seconds=30)
    
    return {"data": data, "source": "generated"}

@app.get(
    "/random-user",
    response_model=RandomUserResponse,
    summary="Получить случайного пользователя",
    description="""Генерирует случайного пользователя с имитацией задержки сервера.
    Результат кешируется на 60 секунд.""",
    tags=["Генератор пользователей"],
    responses={
        200: {
            "description": "Успешный ответ",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "id": 1234,
                            "name": "Иван Петров",
                            "age": 30,
                            "email": "user123@example.com"
                        },
                        "source": "generated"
                    }
                }
            }
        }
    }
)
async def get_random_user():
    """
    Генерация случайного пользователя:
    
    - Проверяет кеш Redis
    - Если нет в кеше, генерирует нового пользователя с задержкой 0.5-3 сек
    - Сохраняет результат в кеш на 60 секунд
    
    Returns:
        Словарь с данными пользователя и источником данных (cache/generated)
    """
    cache_key = "random_user"
    
    cached = await get_cached_data(cache_key)
    if cached:
        return {"data": json.loads(cached), "source": "cache"}
    
    await asyncio.sleep(random.uniform(0.5, 3.0))
    
    first_names = ["Алексей", "Мария", "Иван", "Ольга", "Дмитрий"]
    last_names = ["Петров", "Сидорова", "Иванов", "Смирнова", "Кузнецов"]
    data = {
        "id": random.randint(1000, 9999),
        "name": f"{random.choice(first_names)} {random.choice(last_names)}",
        "age": random.randint(18, 65),
        "email": f"user{random.randint(100, 999)}@example.com"
    }
    
    await set_cached_data(cache_key, json.dumps(data), expire_seconds=60)
    
    return {"data": data, "source": "generated"}

if __name__ == "__main__":    
    uvicorn.run(app, host="0.0.0.0", port=8000)
