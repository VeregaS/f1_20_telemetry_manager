import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from src.models import TelemetryData, Lap

def get_telemetry_df(db: Session, lap_id: int) -> pd.DataFrame:
    """Извлекает телеметрию круга и возвращает DataFrame."""
    query = db.query(TelemetryData).filter(TelemetryData.lap_id == lap_id).order_by(TelemetryData.lap_distance)
    df = pd.read_sql(query.statement, query.session.bind)
    return df

def interpolate_lap_data(df: pd.DataFrame, max_distance: float, step_m: float = 1.0) -> pd.DataFrame:
    """
    Интерполирует данные телеметрии с заданным шагом по дистанции.
    Используется линейная интерполяция numpy для скорости и педалей.
    """
    if df.empty:
        return pd.DataFrame()

    # Удаляем дубликаты по дистанции, если они возникли при микро-зависаниях игры
    df = df.drop_duplicates(subset=['lap_distance'])
    
    # Создаем единый вектор дистанции
    common_distance = np.arange(0, max_distance, step_m)
    
    interp_df = pd.DataFrame({'lap_distance': common_distance})
    
    # Интерполяция ключевых метрик
    for col in ['speed', 'throttle', 'brake', 'gear', 'steer']:
        interp_df[col] = np.interp(common_distance, df['lap_distance'], df[col])
        
    # Округление передач к ближайшему целому (не бывает "полуторной" передачи)
    interp_df['gear'] = interp_df['gear'].round().astype(int)
    
    # Расчет времени прохождения каждого интервала (dt = dx / v)
    # v_ms = speed_kmh / 3.6. Предотвращаем деление на ноль.
    v_ms = np.maximum(interp_df['speed'] / 3.6, 0.1) 
    dt = step_m / v_ms
    
    # Кумулятивная сумма времени (в секундах)
    interp_df['elapsed_time'] = np.cumsum(dt)
    
    return interp_df

def calculate_time_delta(ref_df: pd.DataFrame, comp_df: pd.DataFrame) -> pd.Series:
    """
    Рассчитывает дельту времени между сравниваемым и эталонным кругом.
    Отрицательное значение означает, что сравниваемый круг быстрее.
    """
    # Выравнивание массивов по минимальной длине (на случай схода или недоезда)
    min_len = min(len(ref_df), len(comp_df))
    
    delta = comp_df['elapsed_time'].iloc[:min_len] - ref_df['elapsed_time'].iloc[:min_len]
    return delta

def detect_driving_differences(ref_df: pd.DataFrame, comp_df: pd.DataFrame) -> list[Dict[str, Any]]:
    """
    Алгоритм автоматического поиска критических отличий в пилотировании.
    Анализирует точки торможения и минимальные скорости (апексы).
    """
    insights = []
    
    # Поиск зон жесткого торможения (тормоз > 0.5)
    ref_braking = ref_df[ref_df['brake'] > 0.5]
    comp_braking = comp_df[comp_df['brake'] > 0.5]
    
    # Упрощенная логика: сравниваем дистанцию начала первого торможения
    if not ref_braking.empty and not comp_braking.empty:
        ref_first_brake_dist = ref_braking.iloc[0]['lap_distance']
        comp_first_brake_dist = comp_braking.iloc[0]['lap_distance']
        
        diff_m = comp_first_brake_dist - ref_first_brake_dist
        
        if abs(diff_m) > 10:  # Порог чувствительности: 10 метров
            status = "позже" if diff_m > 0 else "раньше"
            insights.append({
                'type': 'braking',
                'message': f"Первое жесткое торможение начато на {abs(diff_m):.1f} м {status} эталона.",
                'distance': comp_first_brake_dist
            })

    # Сравнение средней скорости
    ref_avg_speed = ref_df['speed'].mean()
    comp_avg_speed = comp_df['speed'].mean()
    if comp_avg_speed < ref_avg_speed:
         insights.append({
                'type': 'speed',
                'message': f"Средняя скорость на {ref_avg_speed - comp_avg_speed:.1f} км/ч ниже эталона.",
                'distance': 0
            })

    return insights

def perform_lap_analysis(db: Session, reference_lap_id: int, compare_lap_id: int) -> Tuple[pd.DataFrame, pd.DataFrame, list]:
    """Основной фасад для генерации аналитики, используемый в Streamlit."""
    ref_raw = get_telemetry_df(db, reference_lap_id)
    comp_raw = get_telemetry_df(db, compare_lap_id)
    
    if ref_raw.empty or comp_raw.empty:
        return pd.DataFrame(), pd.DataFrame(), [{'type': 'speed', 'message': 'Данные для круга еще не записаны или повреждены.'}]
        
    # Определяем общую дистанцию (по самому длинному массиву)
    max_dist = max(ref_raw['lap_distance'].max(), comp_raw['lap_distance'].max())
    
    ref_interp = interpolate_lap_data(ref_raw, max_dist)
    comp_interp = interpolate_lap_data(comp_raw, max_dist)
    
    comp_interp['time_delta'] = calculate_time_delta(ref_interp, comp_interp)
    insights = detect_driving_differences(ref_interp, comp_interp)
    
    return ref_interp, comp_interp, insights