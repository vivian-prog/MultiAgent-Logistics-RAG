# configs/loader.py
"""配置文件加载工具"""
import os
import yaml
from typing import Dict, Any, Optional

# 配置文件路径
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "agent_params.yaml")

# 全局配置缓存
_config_cache: Optional[Dict[str, Any]] = None


def load_config(reload: bool = False) -> Dict[str, Any]:
    """
    加载配置文件
    :param reload: 是否强制重新加载
    :return: 配置字典
    """
    global _config_cache

    if _config_cache is not None and not reload:
        return _config_cache

    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            _config_cache = yaml.safe_load(f)
        return _config_cache
    except FileNotFoundError:
        print(f"警告: 配置文件不存在 {CONFIG_PATH}，使用默认值")
        return get_default_config()
    except Exception as e:
        print(f"警告: 加载配置文件失败 {e}，使用默认值")
        return get_default_config()


def get_default_config() -> Dict[str, Any]:
    """返回默认配置（当配置文件不存在时使用）"""
    return {
        "uav": {
            "max_speed": 0.3,
            "volatility": 0.02,
            "radius": 0.3,
            "tolerance": 0.1,
            "default_max_steps": 1000,
            "default_map_name": "Map1",
            "default_cruise_height": 15,
            "max_height": 20,
            "battery_capacity": 100,
            "battery_drain_rate": 0.5,
        },
        "truck": {
            "base_fuel_per_100km": 30,
            "load_factor": 0.3,
            "speed_factor": 0.005,
            "economic_speed": 60,
            "road_type_factors": {
                "motorway": 1.0,
                "trunk": 1.1,
                "primary": 1.2,
                "secondary": 1.3,
                "tertiary": 1.4,
                "residential": 1.5,
                "unclassified": 1.4,
            },
            "fuel_price": 7.5,
            "default_load_weight": 5.0,
            "default_profile": "car",
        },
        "robot": {
            "speed_m_per_sec": 1.0,
            "grip_ratio": 10.0,
            "battery_capacity": 100,
            "battery_drain_per_sec": 0.02,
            "time_scale": 10.0,
        },
        "simulation": {
            "task_timeout": 120,
            "poll_interval": 1,
            "max_retries": 120,
            "origin_lng": 113.70,
            "origin_lat": 22.40,
            "scale_factor": 1000.0,
        },
        "llm": {
            "temperature": 0.7,
            "rag_timeout": 60,
            "llm_timeout": 120,
        },
    }


def get_uav_config() -> Dict[str, Any]:
    """获取UAV配置"""
    return load_config().get("uav", get_default_config()["uav"])


def get_truck_config() -> Dict[str, Any]:
    """获取Truck配置"""
    return load_config().get("truck", get_default_config()["truck"])


def get_robot_config() -> Dict[str, Any]:
    """获取Robot配置"""
    return load_config().get("robot", get_default_config()["robot"])


def get_simulation_config() -> Dict[str, Any]:
    """获取仿真全局配置"""
    return load_config().get("simulation", get_default_config()["simulation"])


def update_config(overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    用覆盖值更新配置（不修改文件，仅内存中更新）
    :param overrides: 覆盖参数，如 {"uav": {"max_speed": 0.5}}
    :return: 更新后的完整配置
    """
    config = load_config()

    def deep_update(base: dict, updates: dict):
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                deep_update(base[key], value)
            else:
                base[key] = value

    deep_update(config, overrides)
    global _config_cache
    _config_cache = config
    return config


# 便捷函数：获取单个参数值
def get_param(section: str, key: str, default: Any = None) -> Any:
    """
    获取单个参数值
    :param section: 配置节名 (uav/truck/robot/simulation/llm)
    :param key: 参数键名
    :param default: 默认值
    :return: 参数值
    """
    config = load_config()
    return config.get(section, {}).get(key, default)
