"""
数据库迁移脚本：为Agent表添加model字段

如果你之前已经创建了数据库，运行此脚本来添加model字段
"""
import asyncio
import aiosqlite
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = "./opinionroom.db"
DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"


async def migrate():
    """执行数据库迁移"""
    if not os.path.exists(DATABASE_PATH):
        print("❌ 数据库文件不存在，无需迁移")
        return
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # 检查model列是否已存在
        cursor = await db.execute("PRAGMA table_info(agents)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if "model" in column_names:
            print("✅ model字段已存在，无需迁移")
            return
        
        print("🔄 开始迁移：添加model字段...")
        
        try:
            # 添加model列
            await db.execute(f"""
                ALTER TABLE agents 
                ADD COLUMN model VARCHAR(200) DEFAULT '{DEFAULT_MODEL}'
            """)
            
            # 更新所有现有记录
            await db.execute(f"""
                UPDATE agents 
                SET model = '{DEFAULT_MODEL}'
                WHERE model IS NULL
            """)
            
            await db.commit()
            print("✅ 迁移成功！所有Agent已设置默认模型")
            
        except Exception as e:
            print(f"❌ 迁移失败: {e}")
            await db.rollback()


if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移工具 - 添加模型选择功能")
    print("=" * 60)
    asyncio.run(migrate())
    print("=" * 60)

