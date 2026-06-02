from sqlalchemy.orm import Session
from models.user import UserModel
from schemas.user import UserCreate
from core.security import hash_password


def get_by_email(db: Session, email: str) -> UserModel | None:
    return db.query(UserModel).filter(UserModel.email == email).first()


def create_user(db: Session, user: UserCreate) -> UserModel:
    new_user = UserModel(
        email=user.email,
        hashed_password=hash_password(user.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
