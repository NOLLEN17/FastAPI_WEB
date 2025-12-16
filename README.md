# Описание
Данный веб-сервис позволяет производить учет книг домашней библиотеки пользователя.

# Как запустить
Сначала клонируйте репозиторий:
```powershell
git clone https://github.com/NOLLEN17/FastAPI_WEB.git
```
Перейдите в этот репозиторий:
```powershell
cd course
```
Установите необходимые зависимости из `requirements.txt`:
```powershell
pip install -r requirements.txt
```
После установки зависимостей необходимо создать `.env`, его содержание:

SECRET_KEY=...

```
Запустите проект, используя комананду:
```powershell
python main.py
```
# Основные технологии
## Back-end
- FastAPI - современный Python фреймворк

- SQLAlchemy + SQLite - ORM для работы с базой данных

- Pydantic - валидация данных

- Uvicorn - ASGI сервер

