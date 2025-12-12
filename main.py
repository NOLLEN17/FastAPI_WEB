
from fastapi import FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.future import select
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
from dotenv import load_dotenv
import uvicorn
import bcrypt
from database import *
from models import *
from schemes import  *


load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 10

app = FastAPI()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')

    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]

    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)

    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]

        return bcrypt.checkpw(password_bytes, hashed_bytes)

    except Exception:
        return False


def create_access_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_jwt_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_session)
) -> User:

    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.post("/register", response_model=TokenResponse, summary="Регистрация", tags=["Пользователь"])
async def register(
        user_data: UserRegister,
        db: AsyncSession = Depends(get_session)
):

    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    if user_data.email:
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

    hashed_password = hash_password(user_data.password)

    new_user = User(
        username=user_data.username,
        hashed_password=hashed_password,
        email=user_data.email,
        full_name=user_data.full_name
    )

    db.add(new_user)
    await db.commit()

    access_token = create_access_token(user_data.username)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

from fastapi.security import OAuth2PasswordRequestForm

@app.post("/login", response_model=TokenResponse, summary="Логин", tags=["Пользователь"])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_session)
):
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    access_token = create_access_token(form_data.username)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@app.get("/me", response_model=UserResponse, summary="Получить данные профиля", tags=["Пользователь"])
async def get_my_profile(
        current_user: User = Depends(get_current_user)
):
    return current_user


@app.get("/me/profile", response_model=UserProfileResponse, summary="Получить все данные профиля, включая книги пользователя", tags=["Пользователь"])
async def get_my_full_profile(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_session)
):

    result = await db.execute(
        select(Book).where(Book.owner_id == current_user.id).order_by(Book.created_at.desc())
    )
    books = result.scalars().all()

    profile_data = {
        **UserResponse.from_orm(current_user).dict(),
        "books_count": len(books),
        "books": [BookResponse.from_orm(book) for book in books]
    }

    return profile_data


@app.put("/me", response_model=UserResponse, summary="Изменить данные пользователя", tags=["Пользователь"])
async def update_my_profile(
        update_data: UserUpdate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_session)
):

    if update_data.email and update_data.email != current_user.email:
        result = await db.execute(
            select(User).where(User.email == update_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )
        current_user.email = update_data.email

    if update_data.full_name is not None:
        current_user.full_name = update_data.full_name

    if update_data.password:
        current_user.hashed_password = hash_password(update_data.password)

    await db.commit()
    await db.refresh(current_user)

    return current_user


@app.post("/books", response_model=BookResponse, summary="Добавить книгу", tags=["Книги"])
async def add_book(
        book_data: BookCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_session)
):

    new_book = Book(
        title=book_data.title,
        author=book_data.author,
        year=book_data.year,
        description=book_data.description,
        owner_id=current_user.id
    )

    db.add(new_book)
    await db.commit()
    await db.refresh(new_book)

    return new_book


@app.get("/books", response_model=List[BookResponse], summary="Получить список всех книг пользователя", tags=["Книги"])
async def get_my_books(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_session),
        skip: int = 0,
        limit: int = 100,
        author: Optional[str] = None,
        title: Optional[str] = None
):

    query = select(Book).where(Book.owner_id == current_user.id)

    if author:
        query = query.where(Book.author.ilike(f"%{author}%"))
    if title:
        query = query.where(Book.title.ilike(f"%{title}%"))

    query = query.order_by(Book.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    books = result.scalars().all()

    return books


@app.get("/books/{book_id}", response_model=BookResponse, summary="Получить книгу пользователя по id", tags=["Книги"])
async def get_book(
        book_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_session)
):

    result = await db.execute(
        select(Book).where(
            Book.id == book_id,
            Book.owner_id == current_user.id
        )
    )
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    return book


@app.put("/books/{book_id}", response_model=BookResponse, summary="Обновить книгу", tags=["Книги"])
async def update_book(
        book_id: int,
        book_data: BookCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_session)
):

    result = await db.execute(
        select(Book).where(
            Book.id == book_id,
            Book.owner_id == current_user.id
        )
    )
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    book.title = book_data.title
    book.author = book_data.author
    book.year = book_data.year
    book.description = book_data.description

    await db.commit()
    await db.refresh(book)

    return book


@app.delete("/books/{book_id}", summary="Удалить книгу", tags=["Книги"])
async def delete_book(
        book_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_session)
):

    result = await db.execute(
        select(Book).where(
            Book.id == book_id,
            Book.owner_id == current_user.id
        )
    )
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    await db.delete(book)
    await db.commit()

    return {"message": "Book deleted successfully"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)







