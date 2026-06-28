import pandas as pd
import numpy as np
from src.analysis import interpolate_lap_data, calculate_time_delta

def test_interpolate_lap_data():
    """Проверка приведения телеметрии к единому вектору дистанции."""
    # Мок сырых данных телеметрии
    raw_df = pd.DataFrame({
        'lap_distance': [0.0, 10.0, 20.0],
        'speed': [100, 150, 200], # км/ч
        'throttle': [0.5, 1.0, 1.0],
        'brake': [0.0, 0.0, 0.0],
        'gear': [3, 4, 5],
        'steer': [0.0, 0.1, 0.0]
    })
    
    max_dist = 20.0
    step = 1.0
    
    interp_df = interpolate_lap_data(raw_df, max_distance=max_dist, step_m=step)
    
    # Проверка длины массива (от 0 до 19 включительно с шагом 1 = 20 точек)
    assert len(interp_df) == 20
    
    # Проверка интерполяции: на дистанции 5м скорость должна быть ровно посередине между 100 и 150
    speed_at_5m = interp_df.loc[interp_df['lap_distance'] == 5.0, 'speed'].values[0]
    assert speed_at_5m == 125.0
    
    # Проверка расчета кумулятивного времени (elapsed_time)
    assert 'elapsed_time' in interp_df.columns
    assert interp_df['elapsed_time'].iloc[-1] > 0

def test_calculate_time_delta():
    """Проверка вычисления дельты времени между кругами."""
    ref_df = pd.DataFrame({'elapsed_time': [0.1, 0.2, 0.3]})
    comp_df = pd.DataFrame({'elapsed_time': [0.1, 0.25, 0.4]})
    
    delta = calculate_time_delta(ref_df, comp_df)
    
    # Если сравниваемый круг медленнее, дельта должна быть положительной
    assert np.isclose(delta.iloc[2], 0.1) # 0.4 - 0.3 = 0.1