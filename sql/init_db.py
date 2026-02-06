import pymysql
import os
import sys

# ================= 数据库配置 =================
# 请根据实际环境修改以下配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'password',  # <--- 请修改为您的数据库密码
    'database': 'hma_llm',   # <--- 请修改为您的数据库名称
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}
# ============================================

def execute_sql_file(filename, connection):
    """读取并执行 SQL 文件"""
    print(f"正在执行文件: {filename} ...")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # 简单的 SQL 语句分割（按分号）
        # 注意：这种简单的分割不支持存储过程或触发器中的分号
        # 如果 SQL 文件很复杂，建议使用专门的 SQL 执行库或 mysql 命令行工具
        statements = sql_content.split(';')

        with connection.cursor() as cursor:
            count = 0
            for statement in statements:
                # 去除空白字符
                stmt = statement.strip()
                if stmt:
                    try:
                        cursor.execute(stmt)
                        count += 1
                    except Exception as e:
                        print(f"  [错误] 执行语句失败: {stmt[:50]}... \n  原因: {e}")

            connection.commit()
            print(f"  成功执行 {count} 条 SQL 语句。")

    except FileNotFoundError:
        print(f"  [错误] 文件未找到: {filename}")
    except Exception as e:
        print(f"  [错误] 读取或执行文件出错: {e}")

def main():
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 要执行的 SQL 文件列表（按顺序）
    sql_files = [
        os.path.join(current_dir, 'uav_landing_points.sql'),
        os.path.join(current_dir, 'insert_uav_landing_points.sql')
    ]

    print("=== 开始初始化数据库 ===")

    conn = None
    try:
        # 尝试连接数据库
        conn = pymysql.connect(**DB_CONFIG)
        print("数据库连接成功！")

        # 依次执行 SQL 文件
        for sql_file in sql_files:
            execute_sql_file(sql_file, conn)

        print("=== 数据库初始化完成 ===")

    except pymysql.MySQLError as e:
        print(f"数据库连接失败: {e}")
        print("请检查 DB_CONFIG 配置是否正确（密码、端口、库名）。")
    except Exception as e:
        print(f"发生未知错误: {e}")
    finally:
        if conn:
            conn.close()
            print("数据库连接已关闭。")

if __name__ == "__main__":
    main()
