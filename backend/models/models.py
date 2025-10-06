from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, Integer
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from services.db_core import Base


# Character Table
class Character(Base):
    __tablename__ = "characters"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, index=True, nullable=False)
    configs = Column(Text, default="{}")  # JSON as a string
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    history = relationship("History", back_populates="character")


# History table
class History(Base):
    __tablename__ = "history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id = Column(String, ForeignKey("characters.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' / 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
    tags = Column(Text, default='[]')

    character = relationship("Character", back_populates="history")
    reasoning = relationship(
        "Reasoning",
        back_populates="message",
        uselist=False,
        cascade="all, delete-orphan",
    )
    media = relationship(
        "Storage",
        back_populates="message",
        cascade="all, delete-orphan",
    )


# =======================
# Users
# =======================
class User(Base):
    __tablename__ = "users"

    uuid = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    trust_level = Column(Integer, default=0)  # 0=anon, 1=friend, 2=owner
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


# =======================
# Messages
# =======================
class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.uuid"), nullable=False)
    dialog_id = Column(String, nullable=True)  # group messages by dialog
    role = Column(String, nullable=False)  # 'user' / 'assistant'
    content = Column(Text, nullable=False)  # plain text for now; encryption later
    volatile = Column(Boolean, default=False)  # temporary message
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
    tags = Column(Text, default='[]')

    user = relationship("User")



class ShortTermMemory(Base):
    __tablename__ = "short_term_memory"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    summary = Column(Text, nullable=False)
    dialogue_ids = Column(Text, nullable=False)
    themes = Column(Text, default='[]')
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Storage(Base):
    __tablename__ = "storage"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(
        String, ForeignKey("history.id", ondelete="CASCADE"), nullable=False
    )
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=False, default="application/octet-stream")
    size = Column(Integer, default=0)
    category = Column(String, nullable=False, default="other")
    description = Column(Text, nullable=True)
    meta = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    message = relationship("History", back_populates="media")


class Reasoning(Base):
    __tablename__ = "reasoning"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(
        String,
        ForeignKey("history.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    message = relationship("History", back_populates="reasoning")


class LorebookEntry(Base):
    __tablename__ = "lorebook_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False, default="Untitled")
    content = Column(Text, nullable=False)
    keywords = Column(Text, default="")
    category = Column(String, default="general")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
