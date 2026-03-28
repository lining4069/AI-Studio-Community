from sqlalchemy import Boolean, Enum, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """
    ⽤户信息表ORM模型
    """

    __tablename__ = "user"
    # 创建索引 (唯一性约束)
    __table_args__ = (
        Index("idx_username", "username", unique=True),
        Index("idx_email", "email", unique=True),
        Index("idx_phone", "phone", unique=True),
    )
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="⽤户ID"
    )
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="⽤户名"
    )
    email: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True, comment="邮箱"
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True, comment="手机号"
    )
    password: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码（加密存储）"
    )
    nickname: Mapped[str | None] = mapped_column(String(50), comment="昵称")
    avatar: Mapped[str | None] = mapped_column(
        String(255),
        comment="头像URL",
        default="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg",
    )
    gender: Mapped[str | None] = mapped_column(
        Enum("male", "female", "unknown"), comment="性别", default="unknown"
    )
    bio: Mapped[str | None] = mapped_column(
        String(500), comment="个⼈简介", default="这个⼈很懒，什么都没留下"
    )
    # 验证状态
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="邮箱是否已验证",
    )
    is_phone_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="手机号是否已验证",
    )
    # 用户状态
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', nickname='{self.nickname}')>"
