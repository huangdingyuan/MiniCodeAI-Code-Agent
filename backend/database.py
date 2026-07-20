from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={
        "charset": "utf8mb4",
        "use_unicode": True
    }
)

async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库表（仅创建不存在的表，保留已有数据）"""
    print("服务启动，初始化数据表...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 对已存在的表执行增量列迁移（不丢失数据）
        await _migrate_users_avatar(conn)
    print("数据表初始化完成")


async def _migrate_users_avatar(conn):
    """为 users 表新增/调整 avatar 列（LONGTEXT 以支持大图 Base64）"""
    from sqlalchemy import text
    try:
        result = await conn.execute(text(
            "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'avatar'"
        ))
        row = result.first()
        if row is None:
            # 列不存在，新增为 LONGTEXT
            await conn.execute(text(
                "ALTER TABLE `users` ADD COLUMN `avatar` LONGTEXT NULL COMMENT '头像URL或Base64数据' AFTER `hashed_password`"
            ))
            print("已迁移：users 表新增 avatar 列（LONGTEXT）")
        elif row[1].lower() != "longtext":
            # 列存在但不是 LONGTEXT，修改类型
            await conn.execute(text(
                "ALTER TABLE `users` MODIFY COLUMN `avatar` LONGTEXT NULL COMMENT '头像URL或Base64数据'"
            ))
            print(f"已迁移：users.avatar 列从 {row[1]} 修改为 LONGTEXT")
    except Exception as e:
        print(f"迁移 users.avatar 列失败（可忽略）：{e}")