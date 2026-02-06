-- 无人机起降点信息表
CREATE TABLE IF NOT EXISTS uav_landing_points (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '起降点ID',
    name VARCHAR(50) NOT NULL COMMENT '起降点名称',
    location_x DECIMAL(12, 6) NOT NULL COMMENT 'GPS经度',
    location_y DECIMAL(12, 6) NOT NULL COMMENT 'GPS纬度',
    description VARCHAR(200) COMMENT '描述信息',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='无人机起降点信息表';

-- 插入一些测试数据（可选）
-- INSERT INTO uav_landing_points (name, location_x, location_y) VALUES ('起降点A', 113.914200, 22.793300);
