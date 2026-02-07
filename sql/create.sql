-- 0. 清理旧表（注意顺序，先删子表）
DROP TABLE IF EXISTS agent_uav_sensor;
DROP TABLE IF EXISTS agent_ground_sensor;
DROP TABLE IF EXISTS agent_warehouse_sensor;
DROP TABLE IF EXISTS task_agent_rel;
DROP TABLE IF EXISTS task_main;
DROP TABLE IF EXISTS agent_base;
DROP TABLE IF EXISTS warehouse_goods;
DROP TABLE IF EXISTS warehouse_base;

-- 1. 仓储基础信息表
CREATE TABLE IF NOT EXISTS warehouse_base (
    warehouse_id INT PRIMARY KEY AUTO_INCREMENT,
    warehouse_name VARCHAR(50) NOT NULL COMMENT '仓储名称',
    location_x DECIMAL(10,2) NOT NULL COMMENT '仓储X坐标',
    location_y DECIMAL(10,2) NOT NULL COMMENT '仓储Y坐标',
    max_capacity INT NOT NULL COMMENT '最大存储容量（件）',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：0=停用，1=正常，2=维护',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_warehouse_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='仓储基础信息表';

-- 2. 货架与物品信息表
CREATE TABLE IF NOT EXISTS warehouse_goods (
    goods_id INT PRIMARY KEY AUTO_INCREMENT,
    warehouse_id INT NOT NULL COMMENT '所属仓储ID',
    shelf_id VARCHAR(20) NOT NULL COMMENT '货架编号（如A-03-12）',
    shelf_x DECIMAL(10,2) NOT NULL COMMENT '货架X坐标',
    shelf_y DECIMAL(10,2) NOT NULL COMMENT '货架Y坐标',
    goods_name VARCHAR(100) NOT NULL COMMENT '物品名称',
    goods_type VARCHAR(30) NOT NULL COMMENT '物品类型',
    goods_weight DECIMAL(8,2) NOT NULL COMMENT '物品重量（kg）',
    stock_quantity INT NOT NULL DEFAULT 0 COMMENT '当前库存',
    target_location VARCHAR(50) NOT NULL COMMENT '目标交付点',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (warehouse_id) REFERENCES warehouse_base(warehouse_id) ON DELETE CASCADE,
    INDEX idx_shelf_id (shelf_id),
    INDEX idx_goods_type (goods_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='货架与物品信息表';

-- 3. Agent基础信息表
CREATE TABLE IF NOT EXISTS agent_base (
    agent_id VARCHAR(20) PRIMARY KEY COMMENT 'Agent唯一标识（如UAV-001）',
    agent_type TINYINT NOT NULL COMMENT '类型：1=无人机，2=地面运输机器人，3=仓储机器人',
    warehouse_id INT COMMENT '所属仓储ID（仓储机器人必填）',
    max_load DECIMAL(8,2) NOT NULL COMMENT '最大载重（kg）',
    max_speed DECIMAL(8,2) NOT NULL COMMENT '最大速度（m/s）',
    battery_capacity INT NOT NULL COMMENT '电池容量（mAh）',
    status TINYINT NOT NULL DEFAULT 0 COMMENT '状态：0=离线，1=待命，2=执行中，3=故障',
    last_maintain_time DATETIME COMMENT '最后维护时间',
    FOREIGN KEY (warehouse_id) REFERENCES warehouse_base(warehouse_id) ON DELETE SET NULL,
    INDEX idx_agent_type (agent_type),
    INDEX idx_agent_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent基础信息表';

-- 4. 任务主表
CREATE TABLE IF NOT EXISTS task_main (
    task_id VARCHAR(50) PRIMARY KEY COMMENT '任务ID（如LOG-20250520-001）',
    task_type TINYINT NOT NULL COMMENT '类型：1=物流运输，2=紧急调货',
    goods_id INT NOT NULL COMMENT '关联物品ID',
    target_x DECIMAL(12,6) NOT NULL COMMENT '目标点X坐标',
    target_y DECIMAL(12,6) NOT NULL COMMENT '目标点Y坐标',
    require_time DATETIME NOT NULL COMMENT '要求完成时间',
    status TINYINT NOT NULL DEFAULT 0 COMMENT '状态：0=未开始，1=执行中，2=完成，3=失败',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    complete_time DATETIME,
    FOREIGN KEY (goods_id) REFERENCES warehouse_goods(goods_id) ON DELETE CASCADE,
    INDEX idx_task_status (status),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务主表';

-- 5. 任务-Agent关联表
CREATE TABLE IF NOT EXISTS task_agent_rel (
    rel_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id VARCHAR(50) NOT NULL COMMENT '关联任务ID',
    agent_id VARCHAR(20) NOT NULL COMMENT '关联AgentID',
    agent_role VARCHAR(20) NOT NULL COMMENT '分工（如取货、地面运输、空中投递）',
    start_time DATETIME NOT NULL COMMENT '开始执行时间',
    end_time DATETIME,
    status TINYINT NOT NULL DEFAULT 0 COMMENT '状态：0=未开始，1=执行中，2=完成',
    feedback_info VARCHAR(200) COMMENT '反馈信息',
    FOREIGN KEY (task_id) REFERENCES task_main(task_id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agent_base(agent_id) ON DELETE CASCADE,
    UNIQUE KEY uk_task_agent (task_id, agent_id),
    INDEX idx_rel_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务-Agent关联表';

-- 6. 无人机传感器数据表
CREATE TABLE IF NOT EXISTS agent_uav_sensor (
    sensor_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    agent_id VARCHAR(20) NOT NULL COMMENT '关联AgentID',
    task_id VARCHAR(50) NOT NULL COMMENT '关联任务ID',
    gps_x DECIMAL(12,6) NOT NULL COMMENT 'GPS经度',
    gps_y DECIMAL(12,6) NOT NULL COMMENT 'GPS纬度',
    altitude DECIMAL(8,2) NOT NULL COMMENT '飞行高度（m）',
    attitude_angle DECIMAL(6,2) NOT NULL COMMENT '姿态角（°）',
    obstacle_dist DECIMAL(8,2) NOT NULL COMMENT '障碍物距离（m）',
    battery_remaining INT NOT NULL COMMENT '剩余电量（%）',
    signal_strength INT NOT NULL COMMENT '通信信号强度（0-100）',
    collect_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agent_base(agent_id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES task_main(task_id) ON DELETE CASCADE,
    INDEX idx_uav_collect_time (collect_time),
    INDEX idx_uav_agent (agent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='无人机传感器数据表';

-- 7. 地面运输机器人传感器数据表（卡车）
CREATE TABLE IF NOT EXISTS agent_ground_sensor (
    sensor_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    agent_id VARCHAR(20) NOT NULL COMMENT '关联AgentID',
    task_id VARCHAR(50) NOT NULL COMMENT '关联任务ID',
    slam_x DECIMAL(10,2) NOT NULL COMMENT 'SLAM定位X坐标',
    slam_y DECIMAL(10,2) NOT NULL COMMENT 'SLAM定位Y坐标',
    speed DECIMAL(6,2) NOT NULL COMMENT '当前速度（m/s）',
    obstacle_dist DECIMAL(8,2) NOT NULL COMMENT '前方障碍物距离（m）',
    goods_status TINYINT NOT NULL COMMENT '物品状态：0=未装载，1=已装载，2=已交付',
    battery_remaining INT NOT NULL COMMENT '剩余电量（%）',
    collect_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agent_base(agent_id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES task_main(task_id) ON DELETE CASCADE,
    INDEX idx_ground_collect_time (collect_time),
    INDEX idx_ground_agent (agent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地面运输机器人传感器数据表';

-- 8. 仓储机器人传感器数据表
CREATE TABLE IF NOT EXISTS agent_warehouse_sensor (
    sensor_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    agent_id VARCHAR(20) NOT NULL COMMENT '关联AgentID',
    task_id VARCHAR(50) NOT NULL COMMENT '关联任务ID',
    shelf_nav_x DECIMAL(10,2) NOT NULL COMMENT '货架导航X坐标',
    shelf_nav_y DECIMAL(10,2) NOT NULL COMMENT '货架导航Y坐标',
    grip_force DECIMAL(6,2) NOT NULL COMMENT '夹持力（N）',
    goods_weight DECIMAL(8,2) NOT NULL COMMENT '抓取物品重量（kg）',
    warehouse_temp DECIMAL(4,1) NOT NULL COMMENT '仓储内温度（℃）',
    battery_remaining INT NOT NULL COMMENT '剩余电量（%）',
    collect_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agent_base(agent_id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES task_main(task_id) ON DELETE CASCADE,
    INDEX idx_warehouse_collect_time (collect_time),
    INDEX idx_warehouse_agent (agent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='仓储机器人传感器数据表';

-- 批量创建完成提示
SELECT '所有表创建成功' AS result;