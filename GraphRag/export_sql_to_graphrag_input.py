import pymysql
import pymysql.cursors
import os
from datetime import datetime
from typing import List, Dict

# ===================== 核心配置 =====================
# 1. MySQL数据库配置
DB_CONFIG = {
    "host": "localhost",
    "user": "huangw293",
    "password": "Huangw293!@#",
    "database": "hma_llm",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor
}

# 2. 输出配置
OUTPUT_DIR = "/home/sysuvis/program/huangw293/MultiAgent-Logistics-RAG/GraphRag/input"  # TXT文件输出目录（会自动创建）
# 需要生成TXT的表列表（可根据需求调整）
TABLES = [
    "warehouse_base",          # 仓储基础信息表
    "warehouse_goods",         # 货架与物品表
    "agent_base",              # Agent基础信息表
    "task_main",               # 任务主表
    "task_agent_rel",          # 任务-Agent关联表
    "agent_uav_sensor",        # 无人机传感器表
    "agent_ground_sensor",     # 地面运输机器人传感器表
    "agent_warehouse_sensor",   # 仓储机器人传感器表
    "uav_landing_points"        # uav起降点基础信息表
]
# 表的中文备注（提升GraphRAG解析可读性）
TABLE_REMARKS = {
    "warehouse_base": "仓储基础信息表：存储仓库的基础属性，如仓库名称、位置、容量等",
    "warehouse_goods": "货架与物品表：存储仓库内货架、物品的关联信息，如物品名称、货架编号、数量等",
    "agent_base": "Agent基础信息表：存储各类Agent的基础属性，如Agent名称、类型、状态等",
    "task_main": "任务主表：存储任务的核心信息，如任务名称、描述、创建时间、状态等",
    "task_agent_rel": "任务-Agent关联表：存储任务与Agent的绑定关系，如任务ID、Agent ID、分配时间等",
    "agent_uav_sensor": "uav传感器表：存储uav传感器数据，如传感器类型、采集值、采集时间等",
    "agent_ground_sensor": "truck传感器表：存储truck的经纬度和传感器数据",
    "agent_warehouse_sensor": "robot传感器表：存储robot的经纬度传感器数据",
    "uav_landing_points" :  "uav起降点基础信息表：存储uav的经纬度传感器数据"
}

# ===================== 核心工具类 =====================
class GraphRAGInitTxtGenerator:
    def __init__(self):
        self.connection = None
        self.cursor = None
        # 创建输出目录
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"✅ 输出目录已创建/存在：{os.path.abspath(OUTPUT_DIR)}")

    def connect_db(self) -> bool:
        """连接MySQL数据库"""
        try:
            self.connection = pymysql.connect(**DB_CONFIG)
            self.cursor = self.connection.cursor()
            print(f"✅ MySQL数据库连接成功 | 数据库：{DB_CONFIG['database']}")
            return True
        except Exception as e:
            print(f"❌ MySQL连接失败：{str(e)}")
            return False

    def close_db(self):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        print("✅ MySQL连接已关闭")

    def format_value(self, value) -> str:
        """格式化字段值（处理特殊类型）"""
        if value is None:
            return "NULL"
        elif isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, (int, float, bool)):
            return str(value)
        else:
            # 字符串去空格、转义（避免解析问题）
            return str(value).strip().replace("\n", " ").replace("\r", " ")

    def get_table_structure(self, table_name: str) -> List[Dict]:
        """获取表结构（字段名、类型、是否主键、备注）"""
        try:
            self.cursor.execute(f"DESCRIBE {table_name}")
            structure = self.cursor.fetchall()
            # 格式化表结构
            formatted_structure = []
            for field in structure:
                formatted_structure.append({
                    "字段名": field["Field"],
                    "类型": field["Type"],
                    "是否为空": "否" if field["Null"] == "NO" else "是",
                    "主键": "是" if field["Key"] == "PRI" else "否",
                    "默认值": self.format_value(field["Default"]),
                    "额外属性": field["Extra"]
                })
            return formatted_structure
        except Exception as e:
            print(f"❌ 获取{table_name}表结构失败：{str(e)}")
            return []

    def get_table_data(self, table_name: str) -> List[Dict]:
        """获取表的全量数据"""
        try:
            self.cursor.execute(f"SELECT * FROM {table_name}")
            data = self.cursor.fetchall()
            # 格式化数据
            formatted_data = []
            for row in data:
                formatted_row = {}
                for k, v in row.items():
                    formatted_row[k] = self.format_value(v)
                formatted_data.append(formatted_row)
            return formatted_data
        except Exception as e:
            print(f"❌ 获取{table_name}表数据失败：{str(e)}")
            return []

    def generate_table_txt(self, table_name: str):
        """为单个表生成TXT文件（自然语言描述格式）"""
        # 1. 基础信息
        table_remark = TABLE_REMARKS.get(table_name, f"{table_name}表")
        create_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 2. 获取表结构和数据
        table_structure = self.get_table_structure(table_name)
        table_data = self.get_table_data(table_name)
        
        # 3. 构建TXT内容（自然语言描述式格式）
        txt_content = []
        # 头部信息
        txt_content.append("=" * 100)
        txt_content.append(f"表名：{table_name}")
        txt_content.append(f"备注：{table_remark}")
        txt_content.append(f"生成时间：{create_time}")
        txt_content.append(f"数据记录数：{len(table_data)}")
        txt_content.append("=" * 100 + "\n")
        
        # 表结构部分（自然语言描述）
        txt_content.append("【表结构】")
        if table_structure:
            txt_content.append(f"表结构中，有以下字段名，它们的属性如下：")
            # 逐个字段描述属性
            for idx, field in enumerate(table_structure, 1):
                # 处理额外属性为空的情况
                extra_attr = field['额外属性']
                extra_attr_desc = extra_attr if extra_attr.strip() else "为空"
                field_desc = (
                    f"{idx}. 字段名：{field['字段名']}，类型为{field['类型']}，是否可以为空为{field['是否为空']}，"
                    f"是否是主键为{field['主键']}，默认值为{field['默认值']}，额外属性为{extra_attr_desc}。"
                )
                txt_content.append(field_desc)
        else:
            txt_content.append("表结构中暂无可用字段信息")
        txt_content.append("\n" + "-" * 100 + "\n")
        
        # 表数据部分（自然语言键值对描述）
        txt_content.append("【表数据】")
        if table_data:
            txt_content.append(f"表数据记录为：")
            # 逐个数据记录描述
            for data_idx, row in enumerate(table_data, 1):
                # 拼接当前记录的所有键值对
                row_desc_parts = []
                for field, value in row.items():
                    row_desc_parts.append(f"{field}是{value}")
                # 组合成完整的记录描述
                row_desc = f"第{data_idx}个数据：{','.join(row_desc_parts)}。"
                txt_content.append(row_desc)
        else:
            txt_content.append("表数据中暂无可用记录")
        
        # 4. 写入TXT文件
        txt_filename = os.path.join(OUTPUT_DIR, f"{table_name}_init.txt")
        with open(txt_filename, "w", encoding="utf-8") as f:
            f.write("\n".join(txt_content))
        
        print(f"✅ 生成完成：{txt_filename} | 记录数：{len(table_data)}")

    def generate_all_tables_txt(self):
        """生成所有表的TXT文件"""
        if not self.connect_db():
            return
        
        try:
            print(f"\n🚀 开始生成GraphRAG初始化TXT文件（共{len(TABLES)}个表）")
            for table in TABLES:
                print(f"\n处理表：{table}")
                self.generate_table_txt(table)
            
            # 生成汇总文件
            self.generate_summary_file()
            print(f"\n🎉 所有TXT文件生成完成！输出目录：{os.path.abspath(OUTPUT_DIR)}")
        except Exception as e:
            print(f"❌ 生成过程出错：{str(e)}")
        finally:
            self.close_db()

    def generate_summary_file(self):
        """生成文件汇总说明"""
        summary_content = []
        summary_content.append("=" * 100)
        summary_content.append("GraphRAG初始化TXT文件汇总")
        summary_content.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        summary_content.append(f"数据库：{DB_CONFIG['database']}")
        summary_content.append(f"生成表数量：{len(TABLES)}")
        summary_content.append("=" * 100 + "\n")
        
        summary_content.append("【文件列表】")
        for idx, table in enumerate(TABLES, 1):
            summary_content.append(f"{idx}. {table} → {table}_init.txt")
            summary_content.append(f"   备注：{TABLE_REMARKS.get(table, '无备注')}")
        
        summary_content.append(f"\n【使用说明】")
        summary_content.append("1. 所有TXT文件采用自然语言描述格式，可直接作为GraphRAG的输入数据源")
        summary_content.append("2. 执行GraphRAG索引构建命令时，可指定输入目录为：./graphrag_init_txt")
        summary_content.append("3. 建议保留此汇总文件，便于后续维护")
        
        summary_filename = os.path.join(OUTPUT_DIR, "文件汇总说明.txt")
        with open(summary_filename, "w", encoding="utf-8") as f:
            f.write("\n".join(summary_content))
        print(f"✅ 汇总文件生成：{summary_filename}")

# ===================== 执行入口 =====================
if __name__ == "__main__":
    # 初始化生成器
    generator = GraphRAGInitTxtGenerator()
    # 生成所有表的TXT文件
    generator.generate_all_tables_txt()