import argparse
import csv
import os
from datetime import datetime
from pathlib import Path

import pymysql

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = PROJECT_ROOT / "sql" / "vtol_potential_sites.csv"

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "huangw293"),
    "password": os.getenv("MYSQL_PASSWORD", "Huangw293!@#"),
    "database": os.getenv("MYSQL_DATABASE", "hma_llm"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import VTOL potential sites CSV into uav_landing_points."
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        default=str(DEFAULT_CSV),
        help="Path to vtol_potential_sites.csv",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating a backup table before replacing data.",
    )
    return parser.parse_args()


def load_csv(csv_path: Path):
    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"id", "x", "y", "lon", "lat"}
        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing required columns: {sorted(missing)}")

        for row in reader:
            site_id = (row.get("id") or "").strip()
            lon = (row.get("lon") or "").strip()
            lat = (row.get("lat") or "").strip()
            if not site_id or not lon or not lat:
                continue
            rows.append(
                {
                    "name": site_id,
                    "location_x": float(lon),
                    "location_y": float(lat),
                    "description": (
                        "VTOL; "
                        f"grid_x={row.get('x', '').strip()}, grid_y={row.get('y', '').strip()}"
                    ),
                }
            )
    if not rows:
        raise ValueError("No valid VTOL sites found in CSV.")
    return rows


def backup_table(cursor) -> str:
    backup_name = f"uav_landing_points_backup_{datetime.now():%Y%m%d_%H%M%S}"
    cursor.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM uav_landing_points")
    return backup_name


def replace_landing_points(rows, skip_backup: bool) -> None:
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            backup_name = None
            if not skip_backup:
                backup_name = backup_table(cursor)

            cursor.execute("TRUNCATE TABLE uav_landing_points")
            cursor.executemany(
                """
                INSERT INTO uav_landing_points (name, location_x, location_y, description)
                VALUES (%(name)s, %(location_x)s, %(location_y)s, %(description)s)
                """,
                rows,
            )
            connection.commit()

            cursor.execute("SELECT COUNT(*) AS total FROM uav_landing_points")
            total = cursor.fetchone()["total"]

        print("VTOL 起降点导入完成。")
        if backup_name:
            print(f"备份表: {backup_name}")
        print(f"当前 uav_landing_points 记录数: {total}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    args = parse_args()
    csv_path = Path(args.csv_path).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    records = load_csv(csv_path)
    print(f"准备从以下文件导入 {len(records)} 个 VTOL 起降点: {csv_path}")
    replace_landing_points(records, skip_backup=args.no_backup)
