#!/usr/bin/env python
# optimization_algorithms.py
"""
优化算法模块
实现蚁群算法(ACO)和遗传算法(GA)用于物流调度路径优化

使用Python标准库实现，无需额外依赖
"""
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from copy import deepcopy


# ===================== 数据结构定义 =====================
@dataclass
class Location:
    """位置点"""
    id: str
    name: str
    lat: float  # 纬度
    lng: float  # 经度

    def distance_to(self, other: 'Location') -> float:
        """
        计算两点间Haversine距离(单位: km)
        使用简化的欧几里得距离公式以提高效率
        实际生产环境应使用Haversine公式计算球面距离
        """
        # 简化计算: 假设1度约等于111km
        lat_diff = (self.lat - other.lat) * 111.0
        lng_diff = (self.lng - other.lng) * 111.0 * math.cos(math.radians(self.lat))
        return math.sqrt(lat_diff ** 2 + lng_diff ** 2)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, Location):
            return self.id == other.id
        return False


@dataclass
class DeliveryTask:
    """配送任务"""
    task_id: str
    origin: Location           # 起点
    destination: Location      # 终点
    weight: float = 1.0        # 货物重量(kg)
    priority: int = 1          # 优先级 1-5
    agent_type: str = "MIXED"  # ROBOT, TRUCK, UAV, MIXED


@dataclass
class Route:
    """路径"""
    locations: List[Location]
    total_distance: float = 0.0
    total_time: float = 0.0

    def calculate_total_distance(self) -> float:
        """计算路径总距离"""
        self.total_distance = 0.0
        for i in range(len(self.locations) - 1):
            self.total_distance += self.locations[i].distance_to(self.locations[i + 1])
        return self.total_distance


@dataclass
class OptimizationResult:
    """优化结果"""
    algorithm_name: str
    best_route: List[str]              # 最优路径(位置ID列表)
    best_distance: float               # 最优距离(km)
    best_time: float                   # 预估时间(秒)
    iterations: int                    # 迭代次数
    improvement_ratio: float           # 相比初始解的改进比例
    convergence_history: List[float]   # 收敛历史


# ===================== 优化算法基类 =====================
class OptimizationAlgorithm(ABC):
    """优化算法基类"""

    def __init__(self, max_iterations: int = 100, random_seed: int = None):
        self.max_iterations = max_iterations
        if random_seed is not None:
            random.seed(random_seed)

    @abstractmethod
    def optimize(
        self,
        tasks: List[DeliveryTask],
        locations: List[Location]
    ) -> OptimizationResult:
        """
        执行优化
        :param tasks: 配送任务列表
        :param locations: 可用位置列表
        :return: 优化结果
        """
        pass


# ===================== 蚁群算法(ACO) =====================
class AntColonyOptimization(OptimizationAlgorithm):
    """
    蚁群算法实现
    用于解决物流配送路径优化问题(TSP变种)

    核心思想:
    1. 模拟蚂蚁觅食行为，通过信息素引导路径选择
    2. 信息素浓度与路径质量正相关
    3. 信息素会随时间挥发，避免陷入局部最优
    """

    def __init__(
        self,
        max_iterations: int = 100,
        num_ants: int = 20,
        alpha: float = 1.0,      # 信息素重要程度
        beta: float = 2.0,       # 启发函数重要程度
        rho: float = 0.5,        # 信息素挥发系数
        q: float = 100.0,        # 信息素增量系数
        random_seed: int = None
    ):
        super().__init__(max_iterations, random_seed)
        self.num_ants = num_ants
        self.alpha = alpha        # 信息素权重
        self.beta = beta          # 启发信息权重
        self.rho = rho            # 挥发率
        self.q = q                # 信息素强度

        # 信息素矩阵: (from_id, to_id) -> pheromone_value
        self.pheromone_matrix: Dict[Tuple[str, str], float] = {}
        # 距离矩阵缓存
        self.distance_matrix: Dict[Tuple[str, str], float] = {}
        # 位置映射
        self.locations_map: Dict[str, Location] = {}

    def _initialize(self, locations: List[Location]) -> None:
        """初始化信息素矩阵和距离矩阵"""
        self.locations_map = {loc.id: loc for loc in locations}

        # 初始信息素值
        initial_pheromone = 1.0 / len(locations)

        for loc1 in locations:
            for loc2 in locations:
                if loc1.id != loc2.id:
                    key = (loc1.id, loc2.id)
                    self.pheromone_matrix[key] = initial_pheromone
                    self.distance_matrix[key] = loc1.distance_to(loc2)

    def _get_distance(self, from_id: str, to_id: str) -> float:
        """获取两点间距离"""
        return self.distance_matrix.get((from_id, to_id), float('inf'))

    def _get_pheromone(self, from_id: str, to_id: str) -> float:
        """获取两点间信息素浓度"""
        return self.pheromone_matrix.get((from_id, to_id), 0.0)

    def _calculate_probability(
        self,
        current_id: str,
        candidate_id: str
    ) -> float:
        """
        计算从current移动到candidate的概率
        P = (τ^α * η^β) / Σ(τ^α * η^β)
        其中 τ 为信息素浓度, η 为启发函数(距离倒数)
        """
        pheromone = self._get_pheromone(current_id, candidate_id)
        distance = self._get_distance(current_id, candidate_id)

        if distance == 0 or distance == float('inf'):
            return 0.0

        # 启发函数: 距离的倒数
        heuristic = 1.0 / distance

        # 概率值
        return (pheromone ** self.alpha) * (heuristic ** self.beta)

    def _select_next_location(
        self,
        current_id: str,
        unvisited_ids: List[str]
    ) -> str:
        """根据概率选择下一个位置(轮盘赌选择)"""
        probabilities = []
        total_prob = 0.0

        for candidate_id in unvisited_ids:
            prob = self._calculate_probability(current_id, candidate_id)
            probabilities.append((candidate_id, prob))
            total_prob += prob

        if total_prob == 0:
            # 如果所有概率都为0，随机选择
            return random.choice(unvisited_ids)

        # 轮盘赌选择
        r = random.uniform(0, total_prob)
        cumulative = 0.0

        for candidate_id, prob in probabilities:
            cumulative += prob
            if cumulative >= r:
                return candidate_id

        # 兜底返回最后一个
        return probabilities[-1][0]

    def _construct_solution(
        self,
        start_id: str,
        location_ids: List[str]
    ) -> Tuple[List[str], float]:
        """
        构建一条完整路径
        :return: (路径ID列表, 总距离)
        """
        route = [start_id]
        unvisited = [lid for lid in location_ids if lid != start_id]
        total_distance = 0.0
        current_id = start_id

        while unvisited:
            next_id = self._select_next_location(current_id, unvisited)
            total_distance += self._get_distance(current_id, next_id)
            route.append(next_id)
            unvisited.remove(next_id)
            current_id = next_id

        return route, total_distance

    def _update_pheromone(
        self,
        all_routes: List[Tuple[List[str], float]],
        best_route: List[str],
        best_distance: float
    ) -> None:
        """
        更新信息素矩阵
        1. 信息素挥发
        2. 所有蚂蚁释放信息素
        3. 精英蚂蚁额外释放信息素
        """
        # 1. 信息素挥发
        for key in self.pheromone_matrix:
            self.pheromone_matrix[key] *= (1 - self.rho)

        # 2. 所有蚂蚁释放信息素
        for route, distance in all_routes:
            if distance == 0:
                continue
            deposit = self.q / distance
            for i in range(len(route) - 1):
                key = (route[i], route[i + 1])
                if key in self.pheromone_matrix:
                    self.pheromone_matrix[key] += deposit

        # 3. 精英蚂蚁策略: 给最优路径额外信息素
        if best_distance > 0:
            elite_deposit = self.q / best_distance
            for i in range(len(best_route) - 1):
                key = (best_route[i], best_route[i + 1])
                if key in self.pheromone_matrix:
                    self.pheromone_matrix[key] += elite_deposit

    def optimize(
        self,
        tasks: List[DeliveryTask],
        locations: List[Location]
    ) -> OptimizationResult:
        """执行蚁群算法优化"""
        if not locations:
            return OptimizationResult("ACO", [], 0, 0, 0, 0, [])

        # 初始化
        self._initialize(locations)
        location_ids = [loc.id for loc in locations]

        # 起点通常是第一个位置(仓库)
        start_id = location_ids[0]

        best_route = None
        best_distance = float('inf')
        convergence_history = []
        initial_distance = None

        for iteration in range(self.max_iterations):
            all_routes = []

            # 每只蚂蚁构建路径
            for _ in range(self.num_ants):
                route, distance = self._construct_solution(start_id, location_ids)
                all_routes.append((route, distance))

                # 记录初始解
                if initial_distance is None:
                    initial_distance = distance

                # 更新最优解
                if distance < best_distance:
                    best_distance = distance
                    best_route = route.copy()

            # 更新信息素
            self._update_pheromone(all_routes, best_route, best_distance)

            # 记录收敛历史
            convergence_history.append(best_distance)

        # 计算改进比例
        improvement_ratio = 0.0
        if initial_distance and initial_distance > 0:
            improvement_ratio = (initial_distance - best_distance) / initial_distance

        return OptimizationResult(
            algorithm_name="ACO",
            best_route=best_route if best_route else [],
            best_distance=best_distance,
            best_time=best_distance * 60,  # 假设平均速度1km/min
            iterations=self.max_iterations,
            improvement_ratio=improvement_ratio,
            convergence_history=convergence_history
        )


# ===================== 遗传算法(GA) =====================
class GeneticAlgorithm(OptimizationAlgorithm):
    """
    遗传算法实现
    用于解决多阶段调度优化问题

    核心思想:
    1. 模拟生物进化过程: 选择、交叉、变异
    2. 适应度高的个体有更大概率被选中繁殖
    3. 通过交叉和变异产生新个体，探索解空间
    """

    def __init__(
        self,
        max_iterations: int = 100,
        population_size: int = 50,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.1,
        elite_size: int = 5,
        tournament_size: int = 3,
        random_seed: int = None
    ):
        super().__init__(max_iterations, random_seed)
        self.population_size = population_size
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elite_size = elite_size          # 精英个体数量
        self.tournament_size = tournament_size  # 锦标赛选择规模

        # 位置映射
        self.locations_map: Dict[str, Location] = {}

    def _initialize(self, locations: List[Location]) -> None:
        """初始化位置映射"""
        self.locations_map = {loc.id: loc for loc in locations}

    def _create_individual(self, location_ids: List[str]) -> List[str]:
        """创建一个个体(随机排列的路径)"""
        individual = location_ids.copy()
        random.shuffle(individual)
        return individual

    def _initialize_population(self, location_ids: List[str]) -> List[List[str]]:
        """初始化种群"""
        population = []
        for _ in range(self.population_size):
            population.append(self._create_individual(location_ids))
        return population

    def _calculate_fitness(self, individual: List[str]) -> float:
        """
        计算适应度(距离的倒数)
        适应度越高表示路径越短
        """
        total_distance = 0.0
        for i in range(len(individual) - 1):
            loc1 = self.locations_map.get(individual[i])
            loc2 = self.locations_map.get(individual[i + 1])
            if loc1 and loc2:
                total_distance += loc1.distance_to(loc2)

        # 回到起点的距离
        if len(individual) > 1:
            loc1 = self.locations_map.get(individual[-1])
            loc2 = self.locations_map.get(individual[0])
            if loc1 and loc2:
                total_distance += loc1.distance_to(loc2)

        return 1.0 / total_distance if total_distance > 0 else 0

    def _calculate_distance(self, individual: List[str]) -> float:
        """计算路径总距离"""
        total_distance = 0.0
        for i in range(len(individual) - 1):
            loc1 = self.locations_map.get(individual[i])
            loc2 = self.locations_map.get(individual[i + 1])
            if loc1 and loc2:
                total_distance += loc1.distance_to(loc2)
        return total_distance

    def _tournament_selection(
        self,
        population: List[List[str]],
        fitnesses: List[float]
    ) -> List[str]:
        """锦标赛选择"""
        indices = random.sample(
            range(len(population)),
            min(self.tournament_size, len(population))
        )
        best_idx = max(indices, key=lambda i: fitnesses[i])
        return population[best_idx].copy()

    def _crossover_ox(
        self,
        parent1: List[str],
        parent2: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        顺序交叉(Order Crossover, OX)
        保留父代部分片段，从另一个父代填充剩余位置
        """
        size = len(parent1)
        if size < 2:
            return parent1.copy(), parent2.copy()

        # 随机选择交叉区间
        start, end = sorted(random.sample(range(size), 2))

        # 创建子代
        child1 = [None] * size
        child2 = [None] * size

        # 复制交叉区间
        child1[start:end] = parent1[start:end]
        child2[start:end] = parent2[start:end]

        # 填充剩余位置
        def fill_child(child, other_parent):
            """用另一个父代的基因填充子代"""
            current_pos = end % size
            for gene in other_parent:
                if gene not in child:
                    while child[current_pos] is not None:
                        current_pos = (current_pos + 1) % size
                    child[current_pos] = gene

        fill_child(child1, parent2)
        fill_child(child2, parent1)

        return child1, child2

    def _mutate_swap(self, individual: List[str]) -> List[str]:
        """交换变异: 随机交换两个位置"""
        mutated = individual.copy()
        if len(mutated) >= 2:
            idx1, idx2 = random.sample(range(len(mutated)), 2)
            mutated[idx1], mutated[idx2] = mutated[idx2], mutated[idx1]
        return mutated

    def _mutate_reverse(self, individual: List[str]) -> List[str]:
        """逆转变异: 随机逆转一段区间"""
        mutated = individual.copy()
        if len(mutated) >= 2:
            start, end = sorted(random.sample(range(len(mutated)), 2))
            mutated[start:end] = reversed(mutated[start:end])
        return mutated

    def optimize(
        self,
        tasks: List[DeliveryTask],
        locations: List[Location]
    ) -> OptimizationResult:
        """执行遗传算法优化"""
        if not locations:
            return OptimizationResult("GA", [], 0, 0, 0, 0, [])

        # 初始化
        self._initialize(locations)
        location_ids = [loc.id for loc in locations]

        # 初始化种群
        population = self._initialize_population(location_ids)

        best_individual = None
        best_fitness = 0
        best_distance = float('inf')
        convergence_history = []
        initial_distance = None

        for iteration in range(self.max_iterations):
            # 计算适应度
            fitnesses = [self._calculate_fitness(ind) for ind in population]
            distances = [self._calculate_distance(ind) for ind in population]

            # 记录初始解
            if initial_distance is None:
                initial_distance = min(distances)

            # 更新最优解
            for i, (ind, fit, dist) in enumerate(zip(population, fitnesses, distances)):
                if fit > best_fitness:
                    best_fitness = fit
                    best_individual = ind.copy()
                    best_distance = dist

            # 记录收敛历史
            convergence_history.append(best_distance)

            # 精英保留
            elite_indices = sorted(
                range(len(fitnesses)),
                key=lambda i: fitnesses[i],
                reverse=True
            )[:self.elite_size]
            new_population = [population[i].copy() for i in elite_indices]

            # 生成新个体
            while len(new_population) < self.population_size:
                # 选择
                parent1 = self._tournament_selection(population, fitnesses)
                parent2 = self._tournament_selection(population, fitnesses)

                # 交叉
                if random.random() < self.crossover_rate:
                    child1, child2 = self._crossover_ox(parent1, parent2)
                else:
                    child1, child2 = parent1.copy(), parent2.copy()

                # 变异
                if random.random() < self.mutation_rate:
                    child1 = self._mutate_swap(child1)
                if random.random() < self.mutation_rate:
                    child2 = self._mutate_reverse(child2)

                new_population.extend([child1, child2])

            # 保持种群大小
            population = new_population[:self.population_size]

        # 计算改进比例
        improvement_ratio = 0.0
        if initial_distance and initial_distance > 0:
            improvement_ratio = (initial_distance - best_distance) / initial_distance

        return OptimizationResult(
            algorithm_name="GA",
            best_route=best_individual if best_individual else [],
            best_distance=best_distance,
            best_time=best_distance * 60,  # 假设平均速度1km/min
            iterations=self.max_iterations,
            improvement_ratio=improvement_ratio,
            convergence_history=convergence_history
        )


# ===================== 算法工厂 =====================
def create_algorithm(
    algorithm_type: str,
    max_iterations: int = 100,
    random_seed: int = None,
    **kwargs
) -> OptimizationAlgorithm:
    """
    算法工厂函数
    :param algorithm_type: "ACO" 或 "GA"
    :param max_iterations: 最大迭代次数
    :param random_seed: 随机种子
    :param kwargs: 算法特定参数
    """
    algorithm_type = algorithm_type.upper()

    if algorithm_type == "ACO":
        return AntColonyOptimization(
            max_iterations=max_iterations,
            num_ants=kwargs.get('num_ants', 20),
            alpha=kwargs.get('alpha', 1.0),
            beta=kwargs.get('beta', 2.0),
            rho=kwargs.get('rho', 0.5),
            q=kwargs.get('q', 100.0),
            random_seed=random_seed
        )
    elif algorithm_type == "GA":
        return GeneticAlgorithm(
            max_iterations=max_iterations,
            population_size=kwargs.get('population_size', 50),
            crossover_rate=kwargs.get('crossover_rate', 0.8),
            mutation_rate=kwargs.get('mutation_rate', 0.1),
            elite_size=kwargs.get('elite_size', 5),
            random_seed=random_seed
        )
    else:
        raise ValueError(f"未知的算法类型: {algorithm_type}")


# ===================== 便捷函数 =====================
def create_default_locations() -> List[Location]:
    """创建默认测试位置(深圳物流网络)"""
    return [
        Location("WAREHOUSE_001", "深圳北仓库", 22.60, 113.98),
        Location("WAREHOUSE_002", "龙华仓储中心", 22.68, 114.03),
        Location("LANDING_001", "光明城站起降点", 22.75, 113.92),
        Location("LANDING_002", "南山配送站起降点", 22.53, 113.93),
        Location("DEST_001", "中山大学深圳校区", 22.80, 113.95),
        Location("DEST_002", "光明区人民医院", 22.75, 113.90),
        Location("DEST_003", "深圳理工大学医院", 22.77, 113.93),
    ]


def create_default_tasks(locations: List[Location]) -> List[DeliveryTask]:
    """创建默认测试任务"""
    loc_map = {loc.id: loc for loc in locations}

    return [
        DeliveryTask(
            "TASK_001",
            loc_map["WAREHOUSE_001"],
            loc_map["DEST_001"],
            weight=1.2,
            priority=1,
            agent_type="MIXED"
        ),
        DeliveryTask(
            "TASK_002",
            loc_map["WAREHOUSE_002"],
            loc_map["DEST_002"],
            weight=5.0,
            priority=2,
            agent_type="TRUCK"
        ),
    ]


def run_optimization(
    algorithm_type: str,
    locations: List[Location] = None,
    tasks: List[DeliveryTask] = None,
    max_iterations: int = 100,
    random_seed: int = 42,
    verbose: bool = True,
    **kwargs
) -> OptimizationResult:
    """
    运行优化算法的便捷函数

    :param algorithm_type: "ACO" 或 "GA"
    :param locations: 位置列表
    :param tasks: 任务列表
    :param max_iterations: 最大迭代次数
    :param random_seed: 随机种子
    :param verbose: 是否打印详细信息
    :param kwargs: 算法特定参数
    :return: 优化结果
    """
    # 使用默认数据
    if locations is None:
        locations = create_default_locations()
    if tasks is None:
        tasks = create_default_tasks(locations)

    # 创建算法实例
    algorithm = create_algorithm(
        algorithm_type,
        max_iterations=max_iterations,
        random_seed=random_seed,
        **kwargs
    )

    if verbose:
        print(f"\n{'='*60}")
        print(f"运行 {algorithm_type} 优化算法")
        print(f"位置数量: {len(locations)}")
        print(f"任务数量: {len(tasks)}")
        print(f"最大迭代: {max_iterations}")
        print(f"{'='*60}")

    # 执行优化
    result = algorithm.optimize(tasks, locations)

    if verbose:
        print(f"\n优化结果:")
        print(f"  最优路径: {' -> '.join(result.best_route)}")
        print(f"  最优距离: {result.best_distance:.2f} km")
        print(f"  预估时间: {result.best_time:.2f} 分钟")
        print(f"  改进比例: {result.improvement_ratio:.2%}")
        print(f"  收敛历史(最后5次): {[f'{d:.2f}' for d in result.convergence_history[-5:]]}")

    return result


def compare_algorithms(
    locations: List[Location] = None,
    tasks: List[DeliveryTask] = None,
    max_iterations: int = 100,
    random_seed: int = 42,
    verbose: bool = True
) -> Dict[str, OptimizationResult]:
    """
    对比不同算法的性能

    :return: {算法名称: 优化结果}
    """
    if locations is None:
        locations = create_default_locations()
    if tasks is None:
        tasks = create_default_tasks(locations)

    results = {}

    for algo_type in ["ACO", "GA"]:
        results[algo_type] = run_optimization(
            algo_type,
            locations=locations,
            tasks=tasks,
            max_iterations=max_iterations,
            random_seed=random_seed,
            verbose=verbose
        )

    if verbose:
        print(f"\n{'='*60}")
        print("算法对比结果")
        print(f"{'='*60}")
        print(f"{'算法':<10} {'最优距离(km)':<15} {'改进比例':<15} {'迭代次数':<10}")
        print("-" * 50)
        for algo, result in results.items():
            print(f"{algo:<10} {result.best_distance:<15.2f} {result.improvement_ratio:<15.2%} {result.iterations:<10}")

        # 确定最优算法
        best_algo = min(results.items(), key=lambda x: x[1].best_distance)
        print(f"\n最优算法: {best_algo[0]} (距离: {best_algo[1].best_distance:.2f} km)")

    return results


# ===================== 测试代码 =====================
if __name__ == "__main__":
    print("=" * 60)
    print("优化算法测试")
    print("=" * 60)

    # 创建测试数据
    locations = create_default_locations()
    tasks = create_default_tasks(locations)

    print(f"\n测试位置数: {len(locations)}")
    print(f"测试任务数: {len(tasks)}")

    # 测试蚁群算法
    print("\n" + "-" * 40)
    print("蚁群算法(ACO)测试")
    print("-" * 40)

    aco_result = run_optimization(
        "ACO",
        locations=locations,
        tasks=tasks,
        max_iterations=50,
        random_seed=42,
        num_ants=15,
        alpha=1.0,
        beta=2.0,
        rho=0.5
    )

    # 测试遗传算法
    print("\n" + "-" * 40)
    print("遗传算法(GA)测试")
    print("-" * 40)

    ga_result = run_optimization(
        "GA",
        locations=locations,
        tasks=tasks,
        max_iterations=50,
        random_seed=42,
        population_size=30,
        crossover_rate=0.8,
        mutation_rate=0.1
    )

    # 算法对比
    print("\n" + "=" * 60)
    compare_algorithms(
        locations=locations,
        tasks=tasks,
        max_iterations=50,
        random_seed=42,
        verbose=True
    )
