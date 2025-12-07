import numpy as np
from scipy.integrate import solve_ivp
from dataclasses import dataclass
from typing import Tuple, List, Optional, Dict
import json
import matplotlib.pyplot as plt

@dataclass
class PrinterParams:
    """Параметры физической модели принтера"""
    # Механические параметры
    mass_x: float = 0.5  # кг, масса каретки X
    mass_y: float = 0.8  # кг, масса каретки Y  
    mass_z: float = 1.2  # кг, масса стола Z
    
    # Жесткость и демпфирование
    k_x: float = 5000.0   # Н/м, жесткость оси X
    k_y: float = 4500.0   # Н/м, жесткость оси Y
    k_z: float = 6000.0   # Н/м, жесткость оси Z
    
    c_x: float = 5.0     # Н·с/м, демпфирование X
    c_y: float = 4.5     # Н·с/м, демпфирование Y
    c_z: float = 6.0     # Н·с/м, демпфирование Z
    
    # Резонансные частоты (из тестов)
    resonance_freq_x: float = 45.0  # Гц
    resonance_freq_y: float = 38.0  # Гц
    
    # Люфты
    backlash_x: float = 0.01  # мм
    backlash_y: float = 0.01  # мм
    
    # Двигатели TMC2209
    max_current: float = 1.4  # А
    steps_per_mm: float = 80.0
    microsteps: int = 16
    
    def to_dict(self) -> Dict:
        return self.__dict__
    
    @classmethod
    def from_calibration(cls, calibration_data: dict):
        """Создание параметров из данных калибровки"""
        return cls(**calibration_data)

class DigitalTwin:
    """Цифровой двойник 3D принтера"""
    
    def __init__(self, params: PrinterParams):
        self.params = params
        
        # Состояние системы [x, x_dot, y, y_dot, z, z_dot]
        self.state = np.zeros(6)
        
        # История для анализа
        self.history = {
            'time': [],
            'position': [],
            'velocity': [],
            'acceleration': [],
            'error': []
        }
        
        # Модель люфта
        self.last_dir_x = 0
        self.last_dir_y = 0
        self.backlash_comp_x = 0
        self.backlash_comp_y = 0
        
    def dynamics(self, t: float, state: np.ndarray, 
                 u: np.ndarray) -> np.ndarray:
        """Уравнения динамики принтера (3 оси)"""
        # u = [F_x, F_y, F_z] - управляющие силы
        
        # Извлечение состояния
        x, xd, y, yd, z, zd = state
        
        # Уравнения для оси X
        F_x = u[0] if len(u) > 0 else 0
        xdd = (F_x - self.params.c_x * xd - self.params.k_x * x) / self.params.mass_x
        
        # Уравнения для оси Y
        F_y = u[1] if len(u) > 1 else 0
        ydd = (F_y - self.params.c_y * yd - self.params.k_y * y) / self.params.mass_y
        
        # Уравнения для оси Z
        F_z = u[2] if len(u) > 2 else 0
        zdd = (F_z - self.params.c_z * zd - self.params.k_z * z) / self.params.mass_z
        
        return np.array([xd, xdd, yd, ydd, zd, zdd])
    
    def apply_backlash(self, target_pos: np.ndarray, 
                       current_pos: np.ndarray) -> np.ndarray:
        """Моделирование люфта в механике"""
        compensated = target_pos.copy()
        
        # Ось X
        dx = target_pos[0] - current_pos[0]
        if abs(dx) > 0.001:  # Порог движения
            dir_x = 1 if dx > 0 else -1
            if dir_x != self.last_dir_x:
                # Смена направления - учитываем люфт
                compensated[0] += dir_x * self.params.backlash_x
                self.last_dir_x = dir_x
        
        # Ось Y
        dy = target_pos[1] - current_pos[1]
        if abs(dy) > 0.001:
            dir_y = 1 if dy > 0 else -1
            if dir_y != self.last_dir_y:
                compensated[1] += dir_y * self.params.backlash_y
                self.last_dir_y = dir_y
                
        return compensated
    
    def simulate_movement(self, trajectory: np.ndarray, 
                          dt: float = 0.001) -> Dict:
        """
        Симуляция движения по траектории
        
        Args:
            trajectory: Массив [time, target_x, target_y, target_z]
            dt: Шаг симуляции
        """
        results = {
            'time': [],
            'target_pos': [],
            'actual_pos': [],
            'velocity': [],
            'acceleration': [],
            'tracking_error': []
        }
        
        current_state = self.state.copy()
        current_time = 0
        
        for i in range(len(trajectory) - 1):
            t_start, x_t, y_t, z_t = trajectory[i]
            t_end, x_next, y_next, z_next = trajectory[i + 1]
            
            # Целевая позиция с учетом люфта
            target_pos = np.array([x_t, y_t, z_t])
            compensated_target = self.apply_backlash(
                target_pos, current_state[[0, 2, 4]]
            )
            
            # Простая ПИД-имитация для расчета управляющей силы
            Kp = np.array([self.params.k_x, self.params.k_y, self.params.k_z]) * 0.1
            Kd = np.array([self.params.c_x, self.params.c_y, self.params.c_z]) * 0.05
            
            error = compensated_target - current_state[[0, 2, 4]]
            error_derivative = -current_state[[1, 3, 5]]
            
            # Управляющее воздействие (сила)
            u = Kp * error + Kd * error_derivative
            
            # Интегрирование динамики
            t_span = (t_start, t_end)
            sol = solve_ivp(
                lambda t, s: self.dynamics(t, s, u),
                t_span,
                current_state,
                max_step=dt,
                rtol=1e-6,
                atol=1e-9
            )
            
            # Сохранение результатов
            for j in range(len(sol.t)):
                results['time'].append(sol.t[j])
                results['target_pos'].append([x_t, y_t, z_t])
                results['actual_pos'].append(sol.y[[0, 2, 4], j])
                results['velocity'].append(sol.y[[1, 3, 5], j])
                results['tracking_error'].append(
                    np.array([x_t, y_t, z_t]) - sol.y[[0, 2, 4], j]
                )
            
            current_state = sol.y[:, -1]
            current_time = t_end
        
        # Расчет ускорений (только если есть данные)
        if len(results['velocity']) > 1:
            velocities = np.array(results['velocity'])
            times = np.array(results['time'])
            
            # Для каждой оси отдельно
            accels = []
            for axis in range(velocities.shape[1]):
                axis_vel = velocities[:, axis]
                axis_accel = np.gradient(axis_vel, times)
                accels.append(axis_accel)
            
            results['acceleration'] = np.column_stack(accels)
        else:
            results['acceleration'] = []
        
        return results
    
    def predict_vibration(self, movement_data: dict) -> Dict:
        """Предсказание вибраций на основе модели"""
        time_data = np.array(movement_data['time'])
        accel_data = np.array(movement_data['acceleration'])
        
        if len(time_data) <= 1 or len(accel_data) == 0:
            return {
                'resonance_excitation': {'x': 0, 'y': 0},
                'vibration_score': 0,
                'dominant_frequency': 0
            }
        
        # Преобразование Фурье для анализа частот
        dt = time_data[1] - time_data[0]
        n = len(time_data)
        
        # Проверяем размерность ускорений
        if accel_data.ndim == 1:
            # Одно измерение
            fft_result = np.fft.fft(accel_data)
        else:
            # Несколько осей, берем первую
            fft_result = np.fft.fft(accel_data[:, 0])
        
        freqs = np.fft.fftfreq(n, dt)
        
        # Нахождение амплитуд на резонансных частотах
        resonance_amp_x = 0
        resonance_amp_y = 0
        
        if self.params.resonance_freq_x > 0:
            resonance_idx_x = np.argmin(np.abs(freqs - self.params.resonance_freq_x))
            if resonance_idx_x < len(fft_result):
                resonance_amp_x = np.abs(fft_result[resonance_idx_x]) / n
        
        if self.params.resonance_freq_y > 0:
            resonance_idx_y = np.argmin(np.abs(freqs - self.params.resonance_freq_y))
            if resonance_idx_y < len(fft_result):
                resonance_amp_y = np.abs(fft_result[resonance_idx_y]) / n
        
        return {
            'resonance_excitation': {
                'x': float(resonance_amp_x),
                'y': float(resonance_amp_y)
            },
            'vibration_score': float(resonance_amp_x + resonance_amp_y),
            'dominant_frequency': float(freqs[np.argmax(np.abs(fft_result))])
        }
    
    def calculate_quality_metrics(self, simulation_results: Dict) -> Dict:
        """Расчет метрик качества печати"""
        tracking_error = np.array(simulation_results['tracking_error'])
        
        if len(tracking_error) == 0:
            return {
                'overall_score': 0,
                'tracking_score': 0,
                'vibration_score': 0,
                'rms_error_mm': 0,
                'max_error_mm': 0,
                'resonance_excitation': {'x': 0, 'y': 0}
            }
        
        # RMS ошибка слежения
        rms_error = np.sqrt(np.mean(tracking_error**2))
        
        # Максимальная ошибка
        max_error = np.max(np.abs(tracking_error))
        
        # Вибрационный анализ
        vibration_data = self.predict_vibration(simulation_results)
        
        # Скоринговые метрики (0-100)
        tracking_score = max(0, 100 - rms_error * 1000)  # Масштабирование
        vibration_score = max(0, 100 - vibration_data['vibration_score'] * 10)
        
        overall_score = 0.7 * tracking_score + 0.3 * vibration_score
        
        return {
            'overall_score': float(overall_score),
            'tracking_score': float(tracking_score),
            'vibration_score': float(vibration_score),
            'rms_error_mm': float(rms_error),
            'max_error_mm': float(max_error),
            'resonance_excitation': vibration_data.get('resonance_excitation', {'x': 0, 'y': 0})
        }