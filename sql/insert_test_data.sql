-- ==============================================
-- HMA_LLM数据库测试数据插入脚本（修复外键约束问题）
-- ==============================================
USE hma_llm; -- 切换到目标数据库
SET NAMES utf8mb4;

-- 关键修复：临时禁用外键约束（允许TRUNCATE关联表）
SET FOREIGN_KEY_CHECKS = 0;

-- 清空所有表（按外键依赖逆序TRUNCATE，避免报错）
TRUNCATE TABLE agent_warehouse_sensor;
TRUNCATE TABLE agent_ground_sensor;
TRUNCATE TABLE agent_uav_sensor;
TRUNCATE TABLE task_agent_rel;
TRUNCATE TABLE task_main;
TRUNCATE TABLE warehouse_goods;
TRUNCATE TABLE agent_base;
TRUNCATE TABLE warehouse_base;

-- 重新启用外键约束
SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------
-- 1. 仓储基础信息表 (warehouse_base) - 10条
-- ----------------------------
INSERT INTO warehouse_base (
    warehouse_name, location_x, location_y, max_capacity, status, create_time, update_time
) VALUES
('北京一号仓储中心', 116.403874, 39.914885, 5000, 1, NOW() - INTERVAL 10 DAY, NOW() - INTERVAL 10 DAY),
('上海二号仓储中心', 121.473701, 31.230416, 8000, 1, NOW() - INTERVAL 9 DAY, NOW() - INTERVAL 9 DAY),
('广州三号仓储中心', 113.264385, 23.129110, 4500, 2, NOW() - INTERVAL 8 DAY, NOW() - INTERVAL 8 DAY),
('深圳四号仓储中心', 114.057868, 22.543096, 6000, 1, NOW() - INTERVAL 7 DAY, NOW() - INTERVAL 7 DAY),
('成都五号仓储中心', 104.065735, 30.659462, 3800, 1, NOW() - INTERVAL 6 DAY, NOW() - INTERVAL 6 DAY),
('杭州六号仓储中心', 120.153576, 30.287459, 7200, 0, NOW() - INTERVAL 5 DAY, NOW() - INTERVAL 5 DAY),
('武汉七号仓储中心', 114.305497, 30.592848, 4200, 1, NOW() - INTERVAL 4 DAY, NOW() - INTERVAL 4 DAY),
('西安八号仓储中心', 108.948024, 34.263161, 3500, 1, NOW() - INTERVAL 3 DAY, NOW() - INTERVAL 3 DAY),
('重庆九号仓储中心', 106.550464, 29.564706, 5800, 2, NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 2 DAY),
('南京十号仓储中心', 118.790790, 32.058324, 4900, 1, NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY);

-- ----------------------------
-- 2. 货架与物品信息表 (warehouse_goods) - 10条
-- ----------------------------
INSERT INTO warehouse_goods (
    warehouse_id, shelf_id, shelf_x, shelf_y, goods_name, goods_type, goods_weight, stock_quantity, target_location, update_time
) VALUES
(1, 'A-01-01', 116.404000, 39.915000, '无人机锂电池', '电子配件', 2.50, 200, '北京朝阳区配送点', NOW() - INTERVAL 10 DAY),
(2, 'B-02-03', 121.474000, 31.230600, '地面机器人轮胎', '机械配件', 8.20, 150, '上海浦东新区配送点', NOW() - INTERVAL 9 DAY),
(3, 'C-03-05', 113.264500, 23.129300, '仓储机器人抓手', '机械配件', 1.80, 80, '广州天河区配送点', NOW() - INTERVAL 8 DAY),
(4, 'D-04-02', 114.058000, 22.543200, '高精度GPS模块', '电子配件', 0.30, 50, '深圳南山区配送点', NOW() - INTERVAL 7 DAY),
(5, 'E-05-08', 104.066000, 30.659600, '物流包装箱(大号)', '包装材料', 0.50, 500, '成都武侯区配送点', NOW() - INTERVAL 6 DAY),
(6, 'F-06-04', 120.153800, 30.287600, '机器人充电底座', '电子设备', 3.80, 30, '杭州西湖区配送点', NOW() - INTERVAL 5 DAY),
(7, 'G-07-06', 114.305700, 30.593000, '数据传输线(3米)', '电子配件', 0.10, 120, '武汉洪山区配送点', NOW() - INTERVAL 4 DAY),
(8, 'H-08-09', 108.948200, 34.263300, '温湿度传感器', '传感设备', 0.20, 40, '西安雁塔区配送点', NOW() - INTERVAL 3 DAY),
(9, 'I-09-07', 106.550600, 29.564900, '干粉灭火器', '安全设备', 1.20, 20, '重庆渝北区配送点', NOW() - INTERVAL 2 DAY),
(10, 'J-10-10', 118.791000, 32.058500, '应急备用电源', '电子设备', 5.60, 15, '南京玄武区配送点', NOW() - INTERVAL 1 DAY);

-- ----------------------------
-- 3. Agent基础信息表 (agent_base) - 10条
-- ----------------------------
INSERT INTO agent_base (
    agent_id, agent_type, warehouse_id, max_load, max_speed, battery_capacity, status, last_maintain_time
) VALUES
('UAV-001', 1, 1, 5.00, 15.00, 10000, 1, NOW() - INTERVAL 30 DAY),
('GROUND-001', 2, 2, 50.00, 2.00, 20000, 2, NOW() - INTERVAL 25 DAY),
('WARE-001', 3, 3, 20.00, 1.00, 15000, 0, NOW() - INTERVAL 20 DAY),
('UAV-002', 1, 4, 8.00, 18.00, 12000, 3, NOW() - INTERVAL 15 DAY),
('GROUND-002', 2, 5, 60.00, 2.50, 25000, 1, NOW() - INTERVAL 10 DAY),
('WARE-002', 3, 6, 25.00, 1.20, 18000, 2, NOW() - INTERVAL 5 DAY),
('UAV-003', 1, 7, 6.50, 16.00, 11000, 1, NOW() - INTERVAL 30 DAY),
('GROUND-003', 2, 8, 55.00, 2.20, 22000, 3, NOW() - INTERVAL 28 DAY),
('WARE-003', 3, 9, 18.00, 0.80, 14000, 1, NOW() - INTERVAL 22 DAY),
('UAV-004', 1, 10, 7.20, 17.00, 11500, 0, NOW() - INTERVAL 18 DAY);

-- ----------------------------
-- 4. 任务主表 (task_main) - 10条
-- ----------------------------
INSERT INTO task_main (
    task_id, task_type, goods_id, target_x, target_y, require_time, status, create_time, complete_time
) VALUES
('LOG-20250520-001', 1, 1, 116.41000000, 39.92000000, NOW() + INTERVAL 1 DAY, 2, NOW() - INTERVAL 10 DAY, NOW() - INTERVAL 9 DAY),
('LOG-20250520-002', 1, 2, 121.48000000, 31.24000000, NOW() + INTERVAL 2 DAY, 1, NOW() - INTERVAL 9 DAY, NULL),
('LOG-20250520-003', 2, 3, 113.27000000, 23.13000000, NOW() + INTERVAL 0.5 DAY, 0, NOW() - INTERVAL 8 DAY, NULL),
('LOG-20250520-004', 1, 4, 114.06000000, 22.55000000, NOW() + INTERVAL 1 DAY, 2, NOW() - INTERVAL 7 DAY, NOW() - INTERVAL 6 DAY),
('LOG-20250520-005', 1, 5, 104.07000000, 30.66000000, NOW() + INTERVAL 1.5 DAY, 1, NOW() - INTERVAL 6 DAY, NULL),
('LOG-20250520-006', 2, 6, 120.16000000, 30.29000000, NOW() + INTERVAL 0.5 DAY, 3, NOW() - INTERVAL 5 DAY, NOW() - INTERVAL 4 DAY),
('LOG-20250520-007', 1, 7, 114.31000000, 30.60000000, NOW() + INTERVAL 1 DAY, 2, NOW() - INTERVAL 4 DAY, NOW() - INTERVAL 3 DAY),
('LOG-20250520-008', 1, 8, 108.95000000, 34.27000000, NOW() + INTERVAL 2 DAY, 0, NOW() - INTERVAL 3 DAY, NULL),
('LOG-20250520-009', 1, 9, 106.56000000, 29.57000000, NOW() + INTERVAL 1.5 DAY, 1, NOW() - INTERVAL 2 DAY, NULL),
('LOG-20250520-010', 2, 10, 118.79500000, 32.06000000, NOW() + INTERVAL 0.5 DAY, 0, NOW() - INTERVAL 1 DAY, NULL);

-- ----------------------------
-- 5. 任务-Agent关联表 (task_agent_rel) - 10条
-- ----------------------------
INSERT INTO task_agent_rel (
    task_id, agent_id, agent_role, start_time, end_time, status, feedback_info
) VALUES
('LOG-20250520-001', 'UAV-001', '空中投递', NOW() - INTERVAL 10 DAY, NOW() - INTERVAL 9 DAY, 2, '投递完成，无异常'),
('LOG-20250520-002', 'GROUND-001', '地面运输', NOW() - INTERVAL 9 DAY, NULL, 1, '运输中，路况良好'),
('LOG-20250520-003', 'WARE-001', '取货', NOW() - INTERVAL 8 DAY, NULL, 0, NULL),
('LOG-20250520-004', 'UAV-002', '空中投递', NOW() - INTERVAL 7 DAY, NOW() - INTERVAL 6 DAY, 2, '投递完成，信号稳定'),
('LOG-20250520-005', 'GROUND-002', '地面运输', NOW() - INTERVAL 6 DAY, NULL, 1, '运输中，接近目标点'),
('LOG-20250520-006', 'WARE-002', '取货', NOW() - INTERVAL 5 DAY, NOW() - INTERVAL 4 DAY, 2, '取货失败，物品缺货'),
('LOG-20250520-007', 'UAV-003', '空中巡检', NOW() - INTERVAL 4 DAY, NOW() - INTERVAL 3 DAY, 2, '巡检完成，无异常'),
('LOG-20250520-008', 'GROUND-003', '地面运输', NOW() - INTERVAL 3 DAY, NULL, 0, NULL),
('LOG-20250520-009', 'WARE-003', '取货', NOW() - INTERVAL 2 DAY, NULL, 1, '取货中，货架定位准确'),
('LOG-20250520-010', 'UAV-004', '空中投递', NOW() - INTERVAL 1 DAY, NULL, 0, NULL);

-- ----------------------------
-- 6. 无人机传感器数据表 (agent_uav_sensor) - 10条
-- ----------------------------
INSERT INTO agent_uav_sensor (
    agent_id, task_id, gps_x, gps_y, altitude, attitude_angle, obstacle_dist, battery_remaining, signal_strength, collect_time
) VALUES
('UAV-001', 'LOG-20250520-001', 116.40500000, 39.91600000, 120.50, 0.00, 5.20, 95, 98, NOW() - INTERVAL 10 DAY + INTERVAL 2 HOUR),
('UAV-001', 'LOG-20250520-001', 116.40600000, 39.91700000, 115.30, 1.20, 4.80, 90, 97, NOW() - INTERVAL 10 DAY + INTERVAL 3 HOUR),
('UAV-002', 'LOG-20250520-004', 114.05900000, 22.54400000, 85.20, 0.80, 3.50, 85, 90, NOW() - INTERVAL 7 DAY + INTERVAL 2 HOUR),
('UAV-002', 'LOG-20250520-004', 114.06000000, 22.54500000, 80.70, 1.00, 2.80, 80, 88, NOW() - INTERVAL 7 DAY + INTERVAL 3 HOUR),
('UAV-003', 'LOG-20250520-007', 114.30600000, 30.59400000, 98.70, 0.50, 4.20, 92, 95, NOW() - INTERVAL 4 DAY + INTERVAL 2 HOUR),
('UAV-003', 'LOG-20250520-007', 114.30700000, 30.59500000, 95.40, 0.30, 3.90, 88, 94, NOW() - INTERVAL 4 DAY + INTERVAL 3 HOUR),
('UAV-004', 'LOG-20250520-010', 118.79200000, 32.05900000, 105.30, 1.50, 6.10, 75, 85, NOW() - INTERVAL 1 DAY + INTERVAL 2 HOUR),
('UAV-004', 'LOG-20250520-010', 118.79300000, 32.06000000, 100.80, 1.10, 5.80, 70, 83, NOW() - INTERVAL 1 DAY + INTERVAL 3 HOUR),
('UAV-001', 'LOG-20250520-001', 116.40700000, 39.91800000, 110.20, 0.70, 4.50, 85, 96, NOW() - INTERVAL 10 DAY + INTERVAL 4 HOUR),
('UAV-002', 'LOG-20250520-004', 114.06100000, 22.54600000, 75.90, 0.90, 3.20, 75, 87, NOW() - INTERVAL 7 DAY + INTERVAL 4 HOUR);

-- ----------------------------
-- 7. 地面运输机器人传感器数据表 (agent_ground_sensor) - 10条
-- ----------------------------
INSERT INTO agent_ground_sensor (
    agent_id, task_id, slam_x, slam_y, speed, obstacle_dist, goods_status, battery_remaining, collect_time
) VALUES
('GROUND-001', 'LOG-20250520-002', 121.475000, 31.231000, 1.20, 2.50, 1, 88, NOW() - INTERVAL 9 DAY + INTERVAL 2 HOUR),
('GROUND-001', 'LOG-20250520-002', 121.476000, 31.232000, 1.10, 3.20, 1, 85, NOW() - INTERVAL 9 DAY + INTERVAL 3 HOUR),
('GROUND-002', 'LOG-20250520-005', 104.067000, 30.660000, 0.80, 1.80, 1, 75, NOW() - INTERVAL 6 DAY + INTERVAL 2 HOUR),
('GROUND-002', 'LOG-20250520-005', 104.068000, 30.661000, 0.90, 2.10, 1, 72, NOW() - INTERVAL 6 DAY + INTERVAL 3 HOUR),
('GROUND-003', 'LOG-20250520-008', 108.949000, 34.264000, 0.00, 0.00, 0, 50, NOW() - INTERVAL 3 DAY + INTERVAL 2 HOUR),
('GROUND-003', 'LOG-20250520-008', 108.949000, 34.264000, 0.00, 0.00, 0, 48, NOW() - INTERVAL 3 DAY + INTERVAL 3 HOUR),
('GROUND-001', 'LOG-20250520-002', 121.477000, 31.233000, 1.00, 2.80, 1, 82, NOW() - INTERVAL 9 DAY + INTERVAL 4 HOUR),
('GROUND-002', 'LOG-20250520-005', 104.069000, 30.662000, 0.70, 2.40, 1, 69, NOW() - INTERVAL 6 DAY + INTERVAL 4 HOUR),
('GROUND-001', 'LOG-20250520-002', 121.478000, 31.234000, 1.10, 3.00, 1, 79, NOW() - INTERVAL 9 DAY + INTERVAL 5 HOUR),
('GROUND-002', 'LOG-20250520-005', 104.070000, 30.663000, 0.80, 2.20, 1, 66, NOW() - INTERVAL 6 DAY + INTERVAL 5 HOUR);

-- ----------------------------
-- 8. 仓储机器人传感器数据表 (agent_warehouse_sensor) - 10条
-- ----------------------------
INSERT INTO agent_warehouse_sensor (
    agent_id, task_id, shelf_nav_x, shelf_nav_y, grip_force, goods_weight, warehouse_temp, battery_remaining, collect_time
) VALUES
('WARE-001', 'LOG-20250520-003', 113.265000, 23.130000, 50.50, 1.80, 25.5, 80, NOW() - INTERVAL 8 DAY + INTERVAL 2 HOUR),
('WARE-001', 'LOG-20250520-003', 113.266000, 23.131000, 48.20, 1.80, 25.6, 78, NOW() - INTERVAL 8 DAY + INTERVAL 3 HOUR),
('WARE-002', 'LOG-20250520-006', 120.154000, 30.288000, 60.30, 3.80, 26.2, 90, NOW() - INTERVAL 5 DAY + INTERVAL 2 HOUR),
('WARE-002', 'LOG-20250520-006', 120.155000, 30.289000, 58.70, 3.80, 26.3, 88, NOW() - INTERVAL 5 DAY + INTERVAL 3 HOUR),
('WARE-003', 'LOG-20250520-009', 106.551000, 29.565000, 45.80, 1.20, 24.8, 85, NOW() - INTERVAL 2 DAY + INTERVAL 2 HOUR),
('WARE-003', 'LOG-20250520-009', 106.552000, 29.566000, 47.20, 1.20, 24.9, 83, NOW() - INTERVAL 2 DAY + INTERVAL 3 HOUR),
('WARE-001', 'LOG-20250520-003', 113.267000, 23.132000, 49.10, 1.80, 25.7, 76, NOW() - INTERVAL 8 DAY + INTERVAL 4 HOUR),
('WARE-002', 'LOG-20250520-006', 120.156000, 30.290000, 59.50, 3.80, 26.4, 86, NOW() - INTERVAL 5 DAY + INTERVAL 4 HOUR),
('WARE-003', 'LOG-20250520-009', 106.553000, 29.567000, 46.50, 1.20, 25.0, 81, NOW() - INTERVAL 2 DAY + INTERVAL 4 HOUR),
('WARE-001', 'LOG-20250520-003', 113.268000, 23.133000, 47.80, 1.80, 25.8, 74, NOW() - INTERVAL 8 DAY + INTERVAL 5 HOUR);

-- ----------------------------
-- 数据插入验证
-- ----------------------------
SELECT '数据插入完成，各表数据量验证：' AS result;
SELECT 'warehouse_base' AS table_name, COUNT(*) AS row_count FROM warehouse_base UNION ALL
SELECT 'warehouse_goods' AS table_name, COUNT(*) AS row_count FROM warehouse_goods UNION ALL
SELECT 'agent_base' AS table_name, COUNT(*) AS row_count FROM agent_base UNION ALL
SELECT 'task_main' AS table_name, COUNT(*) AS row_count FROM task_main UNION ALL
SELECT 'task_agent_rel' AS table_name, COUNT(*) AS row_count FROM task_agent_rel UNION ALL
SELECT 'agent_uav_sensor' AS table_name, COUNT(*) AS row_count FROM agent_uav_sensor UNION ALL
SELECT 'agent_ground_sensor' AS table_name, COUNT(*) AS row_count FROM agent_ground_sensor UNION ALL
SELECT 'agent_warehouse_sensor' AS table_name, COUNT(*) AS row_count FROM agent_warehouse_sensor;