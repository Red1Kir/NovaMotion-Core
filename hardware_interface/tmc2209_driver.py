import serial
import time
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
import struct
import numpy as np  # Добавлен импорт

@dataclass
class TMC2209Config:
    """Конфигурация драйвера TMC2209"""
    uart_address: int = 0
    current: float = 1.2  # А
    microsteps: int = 16
    stealthchop: bool = True
    spreadcycle: bool = False
    stallguard_threshold: int = 0
    coolstep_threshold: int = 0
    
class TMC2209Driver:
    """Драйвер для работы с TMC2209 через UART"""
    
    # Регистры TMC2209
    REG_GCONF = 0x00
    REG_GSTAT = 0x01
    REG_IFCNT = 0x02
    REG_SLAVECONF = 0x03
    REG_IOIN = 0x06
    REG_IHOLD_IRUN = 0x10
    REG_TPOWERDOWN = 0x11
    REG_TSTEP = 0x12
    REG_TPWMTHRS = 0x13
    REG_TCOOLTHRS = 0x14
    REG_THIGH = 0x15
    REG_XDIRECT = 0x2D
    REG_VDCMIN = 0x33
    REG_MSLUT0 = 0x60
    REG_MSLUTSEL = 0x68
    REG_MSLUTSTART = 0x69
    REG_MSCNT = 0x6A
    REG_MSCURACT = 0x6B
    REG_CHOPCONF = 0x6C
    REG_COOLCONF = 0x6D
    REG_DRV_STATUS = 0x6F
    REG_PWMCONF = 0x70
    
    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.config = TMC2209Config()
        
    def connect(self) -> bool:
        """Подключение к драйверу"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0
            )
            time.sleep(0.1)
            
            # Проверка связи
            if self.read_register(self.REG_IOIN):
                print(f"Connected to TMC2209 on {self.port}")
                return True
        except Exception as e:
            print(f"Connection failed: {e}")
        return False
    
    def disconnect(self):
        """Отключение"""
        if self.serial:
            self.serial.close()
            self.serial = None
    
    def calculate_crc(self, data: bytes) -> int:
        """Расчет CRC8 для TMC2209"""
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x07
                else:
                    crc <<= 1
                crc &= 0xFF
        return crc
    
    def build_packet(self, address: int, register: int, 
                    data: int = 0, read: bool = False) -> bytes:
        """Построение пакета для UART"""
        sync = 0x05  # Sync byte
        
        if read:
            # Read packet: [Sync, Address, Register, 0]
            packet = bytes([sync, address, register, 0])
        else:
            # Write packet: [Sync, Address, Register, Data3, Data2, Data1, Data0]
            data_bytes = data.to_bytes(4, 'big')
            packet = bytes([sync, address, register]) + data_bytes
        
        # Добавляем CRC
        crc = self.calculate_crc(packet)
        packet += bytes([crc])
        
        return packet
    
    def send_packet(self, packet: bytes) -> bytes:
        """Отправка пакета и чтение ответа"""
        if not self.serial:
            return b''
        
        self.serial.write(packet)
        time.sleep(0.001)  # Задержка для ответа
        
        # Чтение ответа
        response = self.serial.read(8)  # 8 байт для чтения
        return response
    
    def read_register(self, register: int) -> Optional[int]:
        """Чтение регистра"""
        packet = self.build_packet(self.config.uart_address, 
                                 register, read=True)
        response = self.send_packet(packet)
        
        if len(response) >= 8:
            # Проверка CRC
            received_crc = response[-1]
            calculated_crc = self.calculate_crc(response[:-1])
            
            if received_crc == calculated_crc:
                # Извлечение данных (байты 3-6)
                data = int.from_bytes(response[3:7], 'big')
                return data
        
        return None
    
    def write_register(self, register: int, value: int) -> bool:
        """Запись в регистр"""
        packet = self.build_packet(self.config.uart_address, 
                                 register, value, read=False)
        response = self.send_packet(packet)
        
        # Для записи проверяем только что пакет отправлен
        return len(response) > 0
    
    def setup_driver(self, config: TMC2209Config) -> bool:
        """Настройка драйвера"""
        self.config = config
        
        try:
            # 1. Настройка GCONF
            gconf = 0
            if config.stealthchop:
                gconf |= (1 << 0)  # Enable stealthChop
            if config.spreadcycle:
                gconf |= (1 << 2)  # Enable spreadCycle
            
            if not self.write_register(self.REG_GCONF, gconf):
                return False
            
            # 2. Настройка тока (IHOLD_IRUN)
            # IRUN (16-23 биты): ток работы (0-31 соответствует 0-2.5A)
            # IHOLD (0-4 биты): ток удержания
            irun = int(config.current * 12.5)  # 0.08A per step
            irun = min(max(irun, 1), 31)
            ihold = max(irun // 2, 1)
            
            ihold_irun = (irun << 16) | (ihold << 0)
            if not self.write_register(self.REG_IHOLD_IRUN, ihold_irun):
                return False
            
            # 3. Настройка микрошагов (CHOPCONF)
            chopconf = self.read_register(self.REG_CHOPCONF) or 0
            
            # Установка микрошагов (MRES: биты 24-27)
            mres_map = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4, 32: 5, 64: 6, 128: 7, 256: 8}
            mres = mres_map.get(config.microsteps, 4)  # По умолчанию 16 микрошагов
            
            chopconf &= ~(0xF << 24)  # Очищаем биты MRES
            chopconf |= (mres << 24)
            
            # Включаем интерполяцию
            chopconf |= (1 << 28)
            
            if not self.write_register(self.REG_CHOPCONF, chopconf):
                return False
            
            # 4. Настройка StallGuard (COOLCONF)
            if config.stallguard_threshold > 0:
                coolconf = (config.stallguard_threshold & 0x3FF) << 16
                if not self.write_register(self.REG_COOLCONF, coolconf):
                    return False
            
            # 5. Настройка TPWMTHRS для перехода между stealthChop и spreadCycle
            if config.stealthchop and config.spreadcycle:
                # Переход на spreadCycle при скорости выше 200 шагов/сек
                tpwmthrs = 200
                if not self.write_register(self.REG_TPWMTHRS, tpwmthrs):
                    return False
            
            print(f"TMC2209 configured: {config.current}A, {config.microsteps}uSteps")
            return True
            
        except Exception as e:
            print(f"Setup error: {e}")
            return False
    
    def read_drv_status(self) -> Dict[str, Any]:
        """Чтение статуса драйвера"""
        status = self.read_register(self.REG_DRV_STATUS)
        if status is None:
            return {}
        
        return {
            'stallguard': (status >> 24) & 0xFF,
            'cs_actual': (status >> 16) & 0x1F,
            'fullsteps_active': (status >> 15) & 0x1,
            'stst': (status >> 0) & 0x1,  # Standstill detected
            'olb': (status >> 1) & 0x1,   # Open load B
            'ola': (status >> 2) & 0x1,   # Open load A
            's2gb': (status >> 3) & 0x1,  # Short to ground B
            's2ga': (status >> 4) & 0x1,  # Short to ground A
            'ot': (status >> 5) & 0x1,    # Overtemperature
            'otpw': (status >> 6) & 0x1,  # Overtemperature pre-warning
        }
    
    def measure_resonance(self, axis: str = 'x', 
                         frequency_range: Tuple[float, float] = (10, 100),
                         steps: int = 20) -> Dict[str, Any]:
        """
        Измерение резонансных частот с помощью StallGuard
        
        Args:
            axis: Ось для измерения
            frequency_range: Диапазон частот (Гц)
            steps: Количество шагов измерения
        """
        print(f"Measuring resonance for {axis}-axis...")
        
        results = {
            'frequencies': [],
            'stallguard_values': [],
            'resonance_peaks': []
        }
        
        # Генерация частот
        freqs = np.linspace(frequency_range[0], frequency_range[1], steps)
        
        for freq in freqs:
            # В реальной системе здесь была бы команда движения
            # Для прототипа симулируем чтение StallGuard
            time.sleep(0.05)
            
            # Считываем значение StallGuard (симулируем)
            # В реальной системе здесь было бы:
            # status = self.read_drv_status()
            # sg_value = status.get('stallguard', 0)
            
            # Симуляция: пик на 45 Гц для оси X, 38 Гц для оси Y
            if axis == 'x':
                sg_value = 100 * np.exp(-((freq - 45)**2) / 50)
            else:
                sg_value = 80 * np.exp(-((freq - 38)**2) / 40)
            
            sg_value += np.random.normal(0, 5)  # Добавляем шум
            
            results['frequencies'].append(freq)
            results['stallguard_values'].append(max(0, sg_value))
            
            print(f"  {freq:.1f}Hz: SG={sg_value:.1f}")
        
        # Поиск пиков резонанса
        sg_values = np.array(results['stallguard_values'])
        
        # Простой алгоритм поиска пиков
        for i in range(1, len(sg_values) - 1):
            if sg_values[i] > sg_values[i-1] and sg_values[i] > sg_values[i+1]:
                if sg_values[i] > np.mean(sg_values) + np.std(sg_values):
                    peak_freq = results['frequencies'][i]
                    results['resonance_peaks'].append({
                        'frequency': peak_freq,
                        'amplitude': float(sg_values[i])
                    })
        
        print(f"Found {len(results['resonance_peaks'])} resonance peaks")
        return results
    
    def auto_tune_current(self, target_temp: float = 50.0, 
                         max_current: float = 1.4) -> float:
        """
        Автоматическая настройка тока для целевой температуры
        
        Args:
            target_temp: Целевая температура двигателя (°C)
            max_current: Максимальный допустимый ток (A)
        
        Returns:
            Оптимальный ток (A)
        """
        print("Auto-tuning motor current...")
        
        currents = np.linspace(0.5, max_current, 10)
        optimal_current = 0.8  # По умолчанию
        
        for current in currents:
            # Устанавливаем ток
            self.config.current = current
            self.setup_driver(self.config)
            
            # В реальной системе здесь было бы измерение температуры
            # Для прототипа используем модель
            time.sleep(0.5)
            
            # Читаем статус (имитация измерения температуры)
            status = self.read_drv_status()
            
            # Проверяем перегрев (симулируем)
            simulated_temp = current * 30  # Упрощенная модель
            if simulated_temp > target_temp * 1.2:
                print(f"  {current:.2f}A: Too hot ({simulated_temp:.1f}°C)")
                break
            
            # Имитация: если ток дает хороший результат без ошибок
            optimal_current = current
            print(f"  {current:.2f}A: OK ({simulated_temp:.1f}°C)")
            
            if current >= target_temp / 40:  # Упрощенная модель
                print(f"  Reached target temperature range")
                break
        
        print(f"Optimal current: {optimal_current:.2f}A")
        return optimal_current
    
    def measure_backlash(self, axis: str = 'x') -> float:
        """Измерение люфта (упрощенная версия)"""
        print(f"Measuring backlash for {axis}-axis...")
        
        # В реальной системе здесь были бы команды движения вперед-назад
        # и измерения позиции с датчиков
        
        # Симуляция: возвращаем типичное значение
        backlash = 0.01  # 10 микрон
        
        print(f"  Backlash: {backlash:.3f} mm")
        return backlash