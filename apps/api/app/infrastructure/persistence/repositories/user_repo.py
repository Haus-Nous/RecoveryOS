"""SQLAlchemy implementation of UserRepository and UserIdentityRepository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.identity_repositories import (
    UserIdentityRepository,
    UserRepository,
)
from app.identity.domain.models import User, UserIdentity
from app.identity.domain.types import UserId, UserIdentityId
from app.infrastructure.persistence.models.user import UserIdentityModel, UserModel


class SqlAlchemyUserRepository(UserRepository):
    """PostgreSQL repository for Users."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UserId) -> User | None:
        stmt = select(UserModel).where(UserModel.id == str(user_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return User(
            id=UserId(model.id),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def create(self, user: User) -> User:
        model = UserModel(
            id=str(user.id),
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return user


class SqlAlchemyUserIdentityRepository(UserIdentityRepository):
    """PostgreSQL repository for UserIdentities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_issuer_subject(self, issuer: str, subject: str) -> UserIdentity | None:
        stmt = select(UserIdentityModel).where(
            UserIdentityModel.issuer == issuer,
            UserIdentityModel.subject == subject,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return UserIdentity(
            id=UserIdentityId(model.id),
            user_id=UserId(model.user_id),
            issuer=model.issuer,
            subject=model.subject,
            email=model.email,
            email_verified=model.email_verified,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def create(self, identity: UserIdentity) -> UserIdentity:
        from sqlalchemy.dialects.postgresql import insert

        stmt = (
            insert(UserIdentityModel)
            .values(
                id=str(identity.id),
                user_id=str(identity.user_id),
                issuer=identity.issuer,
                subject=identity.subject,
                email=identity.email,
                email_verified=identity.email_verified,
                created_at=identity.created_at,
                updated_at=identity.updated_at,
            )
            .on_conflict_do_nothing(index_elements=["issuer", "subject"])
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return identity
