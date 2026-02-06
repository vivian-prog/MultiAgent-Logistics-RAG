-- 插入无人机起降点测试数据

-- 1. 中山大学深圳校区起降点 (距离目标点极近)
INSERT INTO uav_landing_points (name, location_x, location_y, description)
VALUES ('中山大学深圳校区起降点', 113.904500, 22.770500, '位于校区北门广场，适合接收医疗物资');

-- 2. 深圳北站起降点 (主要枢纽)
INSERT INTO uav_landing_points (name, location_x, location_y, description)
VALUES ('深圳北站起降点', 114.029000, 22.609000, '交通枢纽中转站');

-- 3. 光明城站起降点
INSERT INTO uav_landing_points (name, location_x, location_y, description)
VALUES ('光明城站起降点', 113.945000, 22.735000, '光明区重要节点');

-- 4. 深圳宝安机场起降点
INSERT INTO uav_landing_points (name, location_x, location_y, description)
VALUES ('宝安机场物流起降点', 113.811000, 22.639000, '航空物流接驳点');

SELECT '无人机起降点数据插入成功' AS result;
