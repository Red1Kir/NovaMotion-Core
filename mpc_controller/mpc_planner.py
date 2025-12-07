import numpy as np
from scipy.optimize import minimize
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
import warnings

@dataclass
class MotionConstraints:
    """Ограничения движения"""
    max_velocity: float = 200.0    # мм/с
    max_acceleration: float = 3000.0  # мм/с²
    max_jerk: float = 50000.0      # мм/с³
    min_velocity: float = 1.0
    
    def validate(self, v: float, a: float, j: float) -> bool:
        return (abs(v) <= self.max_velocity and 
                abs(a) <= self.max_acceleration and 
                abs(j) <= self.max_jerk)

class MPCTrajectoryOptimizer:
    """MPC оптимизатор траектории"""
    
    def __init__(self, dt: float = 0.01, horizon: int = 10):
        self.dt = dt  # шаг дискретизации
        self.horizon = horizon  # горизонт предсказания
        
        # Веса функции стоимости
        self.weights = {
            'tracking': 1.0,      # Ошибка слежения
            'acceleration': 0.1,  # Ускорение
            'jerk': 0.01,         # Рывок
            'vibration': 0.5      # Вибрации
        }
        
    def build_model_matrices(self, mass: float, damping: float, 
                             stiffness: float) -> Tuple[np.ndarray, np.ndarray]:
        """Построение матриц пространства состояний"""
        # Дискретная модель: x_dot = A*x + B*u
        A_cont = np.array([[0, 1],
                          [-stiffness/mass, -damping/mass]])
        
        B_cont = np.array([[0],
                          [1/mass]])
        
        # Дискретизация (простейший метод Эйлера)
        A_disc = np.eye(2) + A_cont * self.dt
        B_disc = B_cont * self.dt
        
        return A_disc, B_disc
    
    def cost_function(self, u_sequence: np.ndarray, *args) -> float:
        """Функция стоимости MPC"""
        x0, target_trajectory, model_params, vibration_penalty = args
        
        n_steps = len(u_sequence) // 3  # 3 оси
        if n_steps == 0:
            return 1e6  # Большая стоимость при пустой последовательности
        
        # Преобразуем в 2D массив
        if u_sequence.ndim == 1:
            u_sequence = u_sequence.reshape((n_steps, 3))
        
        cost = 0.0
        x = x0.copy()
        
        # Используем параметры для оси X (упрощенно)
        A, B = self.build_model_matrices(
            model_params.get('mass_x', 0.5),
            model_params.get('c_x', 5.0),
            model_params.get('k_x', 5000.0)
        )
        
        for k in range(min(n_steps, self.horizon)):
            # Управление
            u = u_sequence[k] if k < len(u_sequence) else np.zeros(3)
            
            # Предсказание состояния (упрощенно для X оси)
            x_next = A @ x[:2] + B * u[0]  # Используем только X компонент
            
            # Ошибка слежения
            if k < len(target_trajectory):
                tracking_error = np.linalg.norm(x_next[0] - target_trajectory[k, 0])
                cost += self.weights['tracking'] * tracking_error**2
            
            # Штраф за ускорение
            acceleration_cost = np.sum(u**2)
            cost += self.weights['acceleration'] * acceleration_cost
            
            # Штраф за рывок (если не первая итерация)
            if k > 0:
                jerk = u - u_sequence[k-1]
                cost += self.weights['jerk'] * np.sum(jerk**2)
            
            # Штраф за вибрации (упрощенный)
            if vibration_penalty is not None and k < len(vibration_penalty):
                cost += self.weights['vibration'] * vibration_penalty[k]
            
            x[:2] = x_next
        
        return cost
    
    def optimize_trajectory(self, start_pos: np.ndarray, 
                           target_pos: np.ndarray,
                           model_params: dict,
                           constraints: MotionConstraints) -> Dict:
        """
        Оптимизация траектории с помощью MPC
        
        Args:
            start_pos: Начальная позиция [x, y, z]
            target_pos: Целевая позиция [x, y, z]
            model_params: Параметры модели
            constraints: Ограничения движения
        """
        # Начальное состояние
        x0 = np.zeros(6)
        x0[[0, 2, 4]] = start_pos
        
        # Создание целевой траектории (линейная интерполяция)
        n_points = self.horizon
        target_trajectory = np.zeros((n_points, 3))
        
        for i in range(3):
            target_trajectory[:, i] = np.linspace(
                start_pos[i], target_pos[i], n_points
            )
        
        # Простая оценка вибраций
        vibration_penalty = np.ones(n_points) * 0.1
        
        # Начальное предположение для управления
        u_init = np.zeros(3 * n_points)
        
        # Ограничения для оптимизации
        bounds = []
        for _ in range(n_points):
            for _ in range(3):
                bounds.append((-constraints.max_acceleration, 
                              constraints.max_acceleration))
        
        # Оптимизация
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = minimize(
                self.cost_function,
                u_init,
                args=(x0, target_trajectory, model_params, vibration_penalty),
                bounds=bounds,
                method='L-BFGS-B',
                options={'maxiter': 100, 'disp': False}
            )
        
        if result.success:
            u_optimal = result.x.reshape((n_points, 3))
            
            # Генерация профиля скорости
            velocity_profile = self._generate_velocity_profile(
                start_pos, target_pos, u_optimal, constraints
            )
            
            return {
                'success': True,
                'control_sequence': u_optimal,
                'velocity_profile': velocity_profile,
                'cost': result.fun
            }
        else:
            # Резервный профиль
            return {
                'success': False,
                'error': result.message,
                'velocity_profile': self._generate_simple_profile(
                    start_pos, target_pos, constraints
                )
            }
    
    def _generate_velocity_profile(self, start: np.ndarray, end: np.ndarray,
                                  u_sequence: np.ndarray,
                                  constraints: MotionConstraints) -> Dict:
        """Генерация плавного профиля скорости"""
        distance = np.linalg.norm(end - start)
        
        if distance < 0.1:
            return {
                'times': [0],
                'velocities': [0],
                'positions': [start.tolist()],
                'accelerations': [0]
            }
        
        # Трапецеидальный профиль
        max_v = min(constraints.max_velocity, 200)
        max_a = min(constraints.max_acceleration, 3000)
        
        # Расчет времени разгона
        t_accel = max_v / max_a
        s_accel = 0.5 * max_a * t_accel**2
        
        if 2 * s_accel > distance:
            # Треугольный профиль
            t_accel = np.sqrt(distance / max_a)
            max_v_actual = max_a * t_accel
            profile = [
                (0, 0, start, 0),
                (t_accel, max_v_actual, (start + end) / 2, max_a),
                (2 * t_accel, 0, end, -max_a)
            ]
        else:
            # Трапецеидальный профиль
            t_coast = (distance - 2 * s_accel) / max_v
            profile = [
                (0, 0, start, 0),
                (t_accel, max_v, start + (end - start) * s_accel / distance, max_a),
                (t_accel + t_coast, max_v, end - (end - start) * s_accel / distance, 0),
                (2 * t_accel + t_coast, 0, end, -max_a)
            ]
        
        times = [p[0] for p in profile]
        velocities = [p[1] for p in profile]
        positions = [p[2].tolist() for p in profile]
        accelerations = [p[3] for p in profile]
        
        return {
            'times': times,
            'velocities': velocities,
            'positions': positions,
            'accelerations': accelerations,
            'max_velocity': max_v if 2 * s_accel <= distance else max_v_actual
        }
    
    def _generate_simple_profile(self, start: np.ndarray, end: np.ndarray,
                                constraints: MotionConstraints) -> Dict:
        """Резервный простой профиль"""
        distance = np.linalg.norm(end - start)
        time = distance / max(constraints.max_velocity, 0.1) if distance > 0 else 1
        
        return {
            'times': [0, time],
            'velocities': [constraints.max_velocity, constraints.max_velocity],
            'positions': [start.tolist(), end.tolist()],
            'accelerations': [0, 0],
            'max_velocity': constraints.max_velocity
        }

class IntelligentPlanner:
    """Интеллигентный планировщик с MPC"""
    
    def __init__(self, twin_model):
        self.twin = twin_model
        self.mpc = MPCTrajectoryOptimizer()
        self.constraints = MotionConstraints()
        
        # Кэш оптимизированных траекторий
        self.trajectory_cache = {}
        
    def plan_movement(self, from_pos: Tuple[float, float, float],
                     to_pos: Tuple[float, float, float]) -> Dict:
        """Планирование движения между двумя точками"""
        
        # Проверка кэша
        cache_key = f"{from_pos}_{to_pos}"
        if cache_key in self.trajectory_cache:
            return self.trajectory_cache[cache_key]
        
        start = np.array(from_pos)
        end = np.array(to_pos)
        
        # Оптимизация траектории
        mpc_result = self.mpc.optimize_trajectory(
            start, end,
            self.twin.params.to_dict(),
            self.constraints
        )
        
        if mpc_result.get('success', False):
            # Симуляция движения через Digital Twin
            trajectory = self._mpc_to_trajectory(mpc_result)
            simulation = self.twin.simulate_movement(trajectory)
            
            # Расчет метрик качества
            quality = self.twin.calculate_quality_metrics(simulation)
            
            result = {
                'planned_trajectory': mpc_result['velocity_profile'],
                'simulation': simulation,
                'quality_metrics': quality,
                'mpc_success': True
            }
        else:
            # Использование простого профиля
            simple_profile = self.mpc._generate_simple_profile(
                start, end, self.constraints
            )
            trajectory = self._profile_to_trajectory(simple_profile)
            simulation = self.twin.simulate_movement(trajectory)
            quality = self.twin.calculate_quality_metrics(simulation)
            
            result = {
                'planned_trajectory': simple_profile,
                'simulation': simulation,
                'quality_metrics': quality,
                'mpc_success': False,
                'warning': 'MPC failed, using simple profile'
            }
        
        # Кэширование результата
        self.trajectory_cache[cache_key] = result
        return result
    
    def _mpc_to_trajectory(self, mpc_result: dict) -> np.ndarray:
        """Конвертация результата MPC в формат траектории"""
        profile = mpc_result['velocity_profile']
        if not profile or 'positions' not in profile:
            return np.array([[0, 0, 0, 0]])
        
        trajectory = []
        time = 0
        positions = profile['positions']
        times = profile.get('times', list(range(len(positions))))
        
        for i in range(len(positions)):
            pos = positions[i]
            if i < len(times):
                time = times[i]
            trajectory.append([time, pos[0], pos[1], pos[2] if len(pos) > 2 else 0])
        
        return np.array(trajectory)
    
    def _profile_to_trajectory(self, profile: dict) -> np.ndarray:
        """Конвертация профиля в траекторию"""
        if not profile or 'positions' not in profile:
            return np.array([[0, 0, 0, 0]])
        
        trajectory = []
        positions = profile['positions']
        times = profile.get('times', list(range(len(positions))))
        
        for i, pos in enumerate(positions):
            t = times[i] if i < len(times) else i
            trajectory.append([t, pos[0], pos[1], pos[2] if len(pos) > 2 else 0])
        
        return np.array(trajectory)
    
    def optimize_print_path(self, gcode_points: List[Tuple[float, float, float]]) -> Dict:
        """Оптимизация полного пути печати"""
        if not gcode_points or len(gcode_points) < 2:
            return {
                'segments': [],
                'average_quality': 0,
                'min_quality': 0,
                'max_quality': 0
            }
        
        optimized_path = []
        quality_scores = []
        
        for i in range(len(gcode_points) - 1):
            result = self.plan_movement(gcode_points[i], gcode_points[i + 1])
            optimized_path.append(result)
            if 'quality_metrics' in result:
                quality_scores.append(result['quality_metrics']['overall_score'])
        
        avg_quality = np.mean(quality_scores) if quality_scores else 0
        
        return {
            'segments': optimized_path,
            'average_quality': float(avg_quality),
            'min_quality': float(min(quality_scores)) if quality_scores else 0,
            'max_quality': float(max(quality_scores)) if quality_scores else 0
        }