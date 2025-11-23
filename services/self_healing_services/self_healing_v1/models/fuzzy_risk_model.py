# self_healing/models/fuzzy_risk_model.py
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

def create_fuzzy_control_system():
    """
    Định nghĩa Hệ thống Mờ với tất cả các thang đo (universe)
    đã được CHUẨN HÓA về [0, 1].
    """
    
    # --- Định nghĩa "Vũ trụ" (Universes) [0, 1] ---
    # np.arange(0, 1.01, 0.01) tạo ra một mảng từ 0.00, 0.01, ..., 1.00
    universe = np.arange(0, 1.01, 0.01)

    # --- Định nghĩa Antecedents (Inputs) [0, 1] ---
    priority = ctrl.Antecedent(universe, 'priority')
    instability = ctrl.Antecedent(universe, 'instability')
    failure_freq = ctrl.Antecedent(universe, 'failure_freq')
    
    # --- Định nghĩa Consequent (Output) [0, 1] ---
    risk_score = ctrl.Consequent(universe, 'risk_score')

    # --- Định nghĩa Hàm thành viên (Membership Functions) ---
    
    # Priority (Thang 0-1)
    # [0, 0, 4] -> [0.0, 0.0, 0.4]
    # [3, 5, 7] -> [0.3, 0.5, 0.7]
    # [6, 10, 10] -> [0.6, 1.0, 1.0]
    priority['Low'] = fuzz.trimf(priority.universe, [0.0, 0.0, 0.4])
    priority['Medium'] = fuzz.trimf(priority.universe, [0.3, 0.5, 0.7])
    priority['High'] = fuzz.trimf(priority.universe, [0.6, 1.0, 1.0])

    # Instability (Thang 0-1, không đổi)
    instability['Stable'] = fuzz.trapmf(instability.universe, [0.0, 0.0, 0.05, 0.1])
    instability['Unstable'] = fuzz.trimf(instability.universe, [0.05, 0.15, 0.3])
    instability['Flaky'] = fuzz.trapmf(instability.universe, [0.25, 0.4, 1.0, 1.0])

    # Failure Frequency (Thang 0-1, không đổi)
    failure_freq['None'] = fuzz.trimf(failure_freq.universe, [0.0, 0.0, 0.1])
    failure_freq['Intermittent'] = fuzz.trimf(failure_freq.universe, [0.1, 0.3, 0.5])
    failure_freq['Frequent'] = fuzz.trapmf(failure_freq.universe, [0.4, 0.6, 1.0, 1.0])
    
    # Risk Score (Thang 0-1)
    # [0, 0, 20, 35] -> [0.0, 0.0, 0.2, 0.35]
    # [30, 50, 70] -> [0.3, 0.5, 0.7]
    # [65, 80, 100, 100] -> [0.65, 0.8, 1.0, 1.0]
    risk_score['Low'] = fuzz.trapmf(risk_score.universe, [0.0, 0.0, 0.2, 0.35])
    risk_score['Medium'] = fuzz.trimf(risk_score.universe, [0.3, 0.5, 0.7])
    risk_score['High'] = fuzz.trapmf(risk_score.universe, [0.65, 0.8, 1.0, 1.0])

    # --- Định nghĩa Luật Mờ (Không thay đổi logic) ---
    rule1 = ctrl.Rule(priority['High'] & instability['Stable'] & failure_freq['Frequent'], risk_score['High'])
    rule2 = ctrl.Rule(instability['Flaky'] & failure_freq['None'], risk_score['Low'])
    rule3 = ctrl.Rule(priority['Low'] & instability['Flaky'], risk_score['Low'])
    rule4 = ctrl.Rule(instability['Unstable'] & failure_freq['Intermittent'], risk_score['Medium'])
    rule5 = ctrl.Rule(priority['High'] & instability['Unstable'], risk_score['Medium'])
    rule6 = ctrl.Rule(priority['High'], risk_score['High'])
    rule7 = ctrl.Rule(priority['Low'], risk_score['Low'])
    rule8 = ctrl.Rule(instability['Flaky'] & failure_freq['Frequent'], risk_score['Medium'])

    return ctrl.ControlSystem([rule1, rule2, rule3, rule4, rule5, rule6, rule7, rule8])

# --- Khởi tạo và Export ---
print("[FuzzyModel] Creating and initializing Normalized [0-1] Fuzzy Control System...")
fuzzy_control_system = create_fuzzy_control_system()
risk_simulator = ctrl.ControlSystemSimulation(fuzzy_control_system)
print("[FuzzyModel] Normalized Fuzzy Control System is ready.")