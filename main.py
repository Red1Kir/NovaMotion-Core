#!/usr/bin/env python3
"""
NovaMotion Core Prototype
Intelligent Motion Planning System for 3D Printers
"""

import sys
import argparse
from digital_twin.printer_model import DigitalTwin, PrinterParams
from mpc_controller.mpc_planner import IntelligentPlanner, MotionConstraints
from hardware_interface.tmc2209_driver import TMC2209Driver, TMC2209Config
from web_visualization.app import app, socketio
import threading
import time

def get_simulated_params():
    """Параметры по умолчанию для симуляции"""
    return PrinterParams(
        mass_x=0.5,
        mass_y=0.8,
        resonance_freq_x=45.0,
        resonance_freq_y=38.0,
        backlash_x=0.01,
        backlash_y=0.01,
        max_current=1.2
    )

def run_calibration(port: str = '/dev/ttyUSB0'):
    """Запуск процедуры калибровки"""
    print("=" * 60)
    print("NovaMotion Core - Auto Calibration")
    print("=" * 60)
    
    # Подключение к TMC2209
    driver = TMC2209Driver(port)
    if not driver.connect():
        print("⚠️  Cannot connect to TMC2209. Using simulated data.")
        return get_simulated_params()
    
    try:
        # 1. Базовая настройка драйвера
        config = TMC2209Config(
            current=1.0,
            microsteps=16,
            stealthchop=True,
            spreadcycle=True
        )
        if not driver.setup_driver(config):
            print("⚠️  Failed to setup driver. Using simulated data.")
            return get_simulated_params()
        
        # 2. Автонастройка тока
        print("\n[1/4] Auto-tuning motor current...")
        optimal_current = driver.auto_tune_current(target_temp=50.0)
        config.current = optimal_current
        driver.setup_driver(config)
        
        # 3. Измерение резонансов
        print("\n[2/4] Measuring resonance frequencies...")
        resonance_results = driver.measure_resonance(
            axis='x',
            frequency_range=(20, 100),
            steps=15
        )
        
        # 4. Измерение люфтов
        print("\n[3/4] Estimating backlash...")
        backlash_x = driver.measure_backlash('x')
        backlash_y = driver.measure_backlash('y')
        
        # 5. Создание параметров модели
        print("\n[4/4] Creating digital twin model...")
        
        # Определяем частоту резонанса
        resonance_freq = 45.0  # по умолчанию
        if resonance_results['resonance_peaks']:
            resonance_freq = resonance_results['resonance_peaks'][0]['frequency']
        
        params = PrinterParams(
            mass_x=0.5,
            mass_y=0.8,
            resonance_freq_x=resonance_freq,
            resonance_freq_y=resonance_freq * 0.85,
            backlash_x=backlash_x,
            backlash_y=backlash_y,
            max_current=optimal_current
        )
        
        print("\n✅ Calibration complete!")
        print(f"   • Resonance X: {params.resonance_freq_x:.1f} Hz")
        print(f"   • Resonance Y: {params.resonance_freq_y:.1f} Hz")
        print(f"   • Optimal current: {optimal_current:.2f} A")
        print(f"   • Backlash X: {backlash_x:.3f} mm")
        print(f"   • Backlash Y: {backlash_y:.3f} mm")
        
        driver.disconnect()
        return params
        
    except Exception as e:
        print(f"⚠️  Calibration error: {e}")
        driver.disconnect()
        return get_simulated_params()

def run_demo():
    """Демонстрация работы системы"""
    print("\n" + "=" * 60)
    print("NovaMotion Core - Demo Sequence")
    print("=" * 60)
    
    # Создание модели
    params = get_simulated_params()
    twin = DigitalTwin(params)
    planner = IntelligentPlanner(twin)
    
    # Демо траектории
    demo_movements = [
        [(0, 0, 0), (100, 0, 0)],    # Быстрое движение
        [(100, 0, 0), (100, 50, 0)],  # Поворот
        [(100, 50, 0), (50, 25, 0)],  # Диагональ
        [(50, 25, 0), (0, 0, 0)],     # Возврат
    ]
    
    for i, (start, end) in enumerate(demo_movements):
        print(f"\nMovement {i+1}: {start} → {end}")
        
        # Планирование
        result = planner.plan_movement(start, end)
        
        # Вывод результатов
        if 'quality_metrics' in result:
            quality = result['quality_metrics']
            print(f"  • Quality score: {quality['overall_score']:.1f}")
            print(f"  • Tracking: {quality['tracking_score']:.1f}")
            print(f"  • Vibration: {quality['vibration_score']:.1f}")
            print(f"  • RMS error: {quality['rms_error_mm']:.3f} mm")
        
        if result.get('mpc_success'):
            print("  • MPC: Optimized trajectory")
        else:
            print("  • MPC: Using simple profile")
        
        time.sleep(0.5)
    
    print("\n✅ Demo complete!")

def main():
    parser = argparse.ArgumentParser(description='NovaMotion Core Prototype')
    parser.add_argument('--mode', choices=['web', 'calibrate', 'demo', 'test'],
                       default='web', help='Operation mode')
    parser.add_argument('--port', default='/dev/ttyUSB0',
                       help='Serial port for TMC2209')
    parser.add_argument('--web-port', type=int, default=5000,
                       help='Web interface port')
    
    args = parser.parse_args()
    
    if args.mode == 'calibrate':
        # Режим калибровки
        run_calibration(args.port)
        
    elif args.mode == 'demo':
        # Демонстрационный режим
        run_demo()
        
    elif args.mode == 'test':
        # Тестовый режим
        print("Running hardware tests...")
        driver = TMC2209Driver(args.port)
        if driver.connect():
            print("✅ TMC2209 connection successful")
            
            # Чтение регистров
            gconf = driver.read_register(driver.REG_GCONF)
            if gconf is not None:
                print(f"✅ GCONF register: 0x{gconf:08X}")
            
            # Чтение статуса
            status = driver.read_drv_status()
            print(f"✅ Driver status: {status}")
            
            driver.disconnect()
        else:
            print("❌ TMC2209 connection failed")
        
    else:
        # Веб-режим (по умолчанию)
        print("\n" + "=" * 60)
        print("NovaMotion Core - Intelligent Motion Planning")
        print("=" * 60)
        print(f"Web interface: http://localhost:{args.web_port}")
        print("Press Ctrl+C to exit")
        print("-" * 60)
        
        # Запуск веб-сервера
        socketio.run(app, debug=False, port=args.web_port, 
                    host='0.0.0.0', allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        sys.exit(0)