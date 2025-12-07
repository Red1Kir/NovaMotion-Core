from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import numpy as np
import json
import threading
import time
from digital_twin.printer_model import DigitalTwin, PrinterParams
from mpc_controller.mpc_planner import IntelligentPlanner, MotionConstraints

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
socketio = SocketIO(app, cors_allowed_origins="*")

# Глобальные объекты
twin_model = None
planner = None
simulation_thread = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/init_printer', methods=['POST'])
def init_printer():
    """Инициализация модели принтера"""
    global twin_model, planner
    
    data = request.json
    
    # Параметры по умолчанию или из запроса
    params = PrinterParams(
        mass_x=data.get('mass_x', 0.5),
        mass_y=data.get('mass_y', 0.8),
        resonance_freq_x=data.get('resonance_x', 45.0),
        resonance_freq_y=data.get('resonance_y', 38.0),
        backlash_x=data.get('backlash_x', 0.01),
        backlash_y=data.get('backlash_y', 0.01)
    )
    
    twin_model = DigitalTwin(params)
    planner = IntelligentPlanner(twin_model)
    
    return jsonify({
        'status': 'success',
        'params': params.to_dict()
    })

@app.route('/api/plan_movement', methods=['POST'])
def plan_movement():
    """Планирование движения"""
    if not planner:
        return jsonify({'error': 'Printer not initialized'}), 400
    
    data = request.json
    from_pos = tuple(data['from'])
    to_pos = tuple(data['to'])
    
    # Планирование движения
    result = planner.plan_movement(from_pos, to_pos)
    
    # Подготовка данных для визуализации
    vis_data = prepare_visualization_data(result)
    
    return jsonify({
        'status': 'success',
        'planning_result': result,
        'visualization': vis_data
    })

@app.route('/api/optimize_gcode', methods=['POST'])
def optimize_gcode():
    """Оптимизация G-кода"""
    if not planner:
        return jsonify({'error': 'Printer not initialized'}), 400
    
    data = request.json
    gcode_points = [tuple(p) for p in data['points']]
    
    # Оптимизация всего пути
    result = planner.optimize_print_path(gcode_points)
    
    return jsonify({
        'status': 'success',
        'optimization': result
    })

@app.route('/api/real_time_simulation', methods=['POST'])
def start_real_time_simulation():
    """Запуск реального времени симуляции"""
    data = request.json
    trajectory = np.array(data['trajectory'])
    
    def simulate_and_stream():
        """Поток симуляции с веб-сокетом"""
        simulation = twin_model.simulate_movement(trajectory, dt=0.01)
        
        for i in range(len(simulation['time'])):
            if i % 10 == 0:  # Отправляем каждые 10 точек
                socketio.emit('simulation_update', {
                    'time': float(simulation['time'][i]),
                    'position': simulation['actual_pos'][i].tolist(),
                    'target': simulation['target_pos'][i].tolist(),
                    'error': simulation['tracking_error'][i].tolist(),
                    'velocity': simulation['velocity'][i].tolist()
                })
                time.sleep(0.01)
        
        socketio.emit('simulation_complete', {
            'quality': twin_model.calculate_quality_metrics(simulation)
        })
    
    # Запуск в отдельном потоке
    global simulation_thread
    simulation_thread = threading.Thread(target=simulate_and_stream)
    simulation_thread.start()
    
    return jsonify({'status': 'simulation_started'})

def prepare_visualization_data(result: dict) -> dict:
    """Подготовка данных для визуализации"""
    sim = result['simulation']
    
    # Уменьшаем количество точек для фронтенда
    step = max(1, len(sim['time']) // 1000)
    
    return {
        'time': sim['time'][::step].tolist(),
        'target_x': [p[0] for p in sim['target_pos'][::step]],
        'target_y': [p[1] for p in sim['target_pos'][::step]],
        'actual_x': [p[0] for p in sim['actual_pos'][::step]],
        'actual_y': [p[1] for p in sim['actual_pos'][::step]],
        'error_x': [e[0] for e in sim['tracking_error'][::step]],
        'error_y': [e[1] for e in sim['tracking_error'][::step]],
        'velocity': [v[0] for v in sim['velocity'][::step]],  # X скорость
        'acceleration': [a[0] for a in sim['acceleration'][::step]],
        'quality_metrics': result['quality_metrics']
    }

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', {'message': 'Connected to NovaMotion Core'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    print("Starting NovaMotion Core Web Interface...")
    print("Open http://localhost:5000 in your browser")
    socketio.run(app, debug=True, port=5000)