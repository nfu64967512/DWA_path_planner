"""
參數面板模組
提供飛行參數、測繪參數的設置界面
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QSlider, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QPushButton, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal

from config import Config
from logger_utils import logger


class ParameterPanel(QWidget):
    """
    參數面板
    
    提供各種飛行和測繪參數的設置
    """
    
    # 信號定義
    parameters_changed = pyqtSignal(dict)  # 參數變更信號
    
    def __init__(self, parent=None):
        """初始化參數面板"""
        super().__init__(parent)
        
        # 初始化參數字典
        self.parameters = {
            'altitude': 50.0,
            'speed': 10.0,
            'angle': 0.0,
            'spacing': 20.0,
            'yaw_speed': 60.0,
            'subdivisions': 1,
            'region_spacing': 3.0,
            'reduce_overlap': True,
            'flight_mode': 'smart_collision'
        }
        
        # 建立 UI
        self.init_ui()
        
        logger.info("參數面板初始化完成")
    
    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 飛行參數群組
        flight_group = self.create_flight_parameters()
        layout.addWidget(flight_group)
        
        # 測繪參數群組
        survey_group = self.create_survey_parameters()
        layout.addWidget(survey_group)
        
        # 進階參數群組
        advanced_group = self.create_advanced_parameters()
        layout.addWidget(advanced_group)
        
        # 添加彈性空間
        layout.addStretch()
    
    def create_flight_parameters(self):
        """創建飛行參數群組"""
        group = QGroupBox("飛行參數")
        layout = QFormLayout(group)
        
        # 飛行高度
        self.altitude_spin = QDoubleSpinBox()
        self.altitude_spin.setRange(Config.SAFETY_SETTINGS.min_altitude_m, 
                                   Config.SAFETY_SETTINGS.max_altitude_m)
        self.altitude_spin.setValue(self.parameters['altitude'])
        self.altitude_spin.setSuffix(" m")
        self.altitude_spin.setDecimals(1)
        self.altitude_spin.valueChanged.connect(lambda v: self.update_parameter('altitude', v))
        layout.addRow("飛行高度:", self.altitude_spin)
        
        # 飛行速度
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(Config.SAFETY_SETTINGS.min_speed_mps, 
                                Config.SAFETY_SETTINGS.max_speed_mps)
        self.speed_spin.setValue(self.parameters['speed'])
        self.speed_spin.setSuffix(" m/s")
        self.speed_spin.setDecimals(1)
        self.speed_spin.valueChanged.connect(lambda v: self.update_parameter('speed', v))
        layout.addRow("飛行速度:", self.speed_spin)
        
        # 轉向速度
        self.yaw_speed_spin = QDoubleSpinBox()
        self.yaw_speed_spin.setRange(10.0, 360.0)
        self.yaw_speed_spin.setValue(self.parameters['yaw_speed'])
        self.yaw_speed_spin.setSuffix(" °/s")
        self.yaw_speed_spin.setDecimals(1)
        self.yaw_speed_spin.valueChanged.connect(lambda v: self.update_parameter('yaw_speed', v))
        layout.addRow("轉向速度:", self.yaw_speed_spin)
        
        return group
    
    def create_survey_parameters(self):
        """創建測繪參數群組"""
        group = QGroupBox("測繪參數")
        layout = QFormLayout(group)
        
        # 掃描角度
        angle_layout = QHBoxLayout()
        self.angle_slider = QSlider(Qt.Orientation.Horizontal)
        self.angle_slider.setRange(-180, 180)
        self.angle_slider.setValue(int(self.parameters['angle']))
        self.angle_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.angle_slider.setTickInterval(30)
        self.angle_label = QLabel(f"{self.parameters['angle']:.0f}°")
        self.angle_slider.valueChanged.connect(self.on_angle_changed)
        angle_layout.addWidget(self.angle_slider)
        angle_layout.addWidget(self.angle_label)
        layout.addRow("掃描角度:", angle_layout)
        
        # 航線間距
        self.spacing_spin = QDoubleSpinBox()
        self.spacing_spin.setRange(Config.SAFETY_SETTINGS.min_spacing_m, 
                                  Config.SAFETY_SETTINGS.max_spacing_m)
        self.spacing_spin.setValue(self.parameters['spacing'])
        self.spacing_spin.setSuffix(" m")
        self.spacing_spin.setDecimals(1)
        self.spacing_spin.valueChanged.connect(lambda v: self.update_parameter('spacing', v))
        layout.addRow("航線間距:", self.spacing_spin)
        
        # 子區域分割
        self.subdivision_combo = QComboBox()
        self.subdivision_combo.addItems(["1 (不分割)", "2 區域", "3 區域", "4 區域 (2x2)"])
        self.subdivision_combo.setCurrentIndex(0)
        self.subdivision_combo.currentIndexChanged.connect(self.on_subdivision_changed)
        layout.addRow("區域分割:", self.subdivision_combo)
        
        # 子區域間距
        self.region_spacing_spin = QDoubleSpinBox()
        self.region_spacing_spin.setRange(0.0, 10.0)
        self.region_spacing_spin.setValue(self.parameters['region_spacing'])
        self.region_spacing_spin.setSuffix(" m")
        self.region_spacing_spin.setDecimals(1)
        self.region_spacing_spin.valueChanged.connect(lambda v: self.update_parameter('region_spacing', v))
        layout.addRow("區域間距:", self.region_spacing_spin)
        
        return group
    
    def create_advanced_parameters(self):
        """創建進階參數群組"""
        group = QGroupBox("進階設定")
        layout = QVBoxLayout(group)
        
        # 減少重疊
        self.reduce_overlap_check = QCheckBox("減少重疊（互補掃描）")
        self.reduce_overlap_check.setChecked(self.parameters['reduce_overlap'])
        self.reduce_overlap_check.stateChanged.connect(
            lambda state: self.update_parameter('reduce_overlap', state == Qt.CheckState.Checked)
        )
        layout.addWidget(self.reduce_overlap_check)
        
        # 飛行模式
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("飛行模式:"))
        self.flight_mode_combo = QComboBox()
        self.flight_mode_combo.addItems(["同步飛行", "智能避撞"])
        self.flight_mode_combo.setCurrentIndex(1)  # 預設智能避撞
        self.flight_mode_combo.currentTextChanged.connect(self.on_flight_mode_changed)
        mode_layout.addWidget(self.flight_mode_combo)
        layout.addLayout(mode_layout)
        
        # 安全距離顯示（只讀）
        safety_layout = QHBoxLayout()
        safety_layout.addWidget(QLabel("安全距離:"))
        safety_label = QLabel(f"{Config.SAFETY_DISTANCE_M} m")
        safety_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        safety_layout.addWidget(safety_label)
        safety_layout.addStretch()
        layout.addLayout(safety_layout)
        
        return group
    
    def on_angle_changed(self, value):
        """處理角度變更"""
        self.angle_label.setText(f"{value}°")
        self.update_parameter('angle', float(value))
    
    def on_subdivision_changed(self, index):
        """處理分割數量變更"""
        subdivisions = index + 1  # 1, 2, 3, 4
        self.update_parameter('subdivisions', subdivisions)
    
    def on_flight_mode_changed(self, text):
        """處理飛行模式變更"""
        mode = 'smart_collision' if text == "智能避撞" else 'synchronous'
        self.update_parameter('flight_mode', mode)
    
    def update_parameter(self, key: str, value):
        """
        更新參數並發送信號
        
        參數:
            key: 參數名稱
            value: 參數值
        """
        self.parameters[key] = value
        self.parameters_changed.emit({key: value})
        logger.debug(f"參數更新: {key} = {value}")
    
    def get_parameters(self):
        """
        獲取所有參數
        
        返回:
            參數字典
        """
        return self.parameters.copy()
    
    def set_parameters(self, params: dict):
        """
        設置參數
        
        參數:
            params: 參數字典
        """
        for key, value in params.items():
            if key in self.parameters:
                self.parameters[key] = value
                
                # 更新 UI
                if key == 'altitude':
                    self.altitude_spin.setValue(value)
                elif key == 'speed':
                    self.speed_spin.setValue(value)
                elif key == 'angle':
                    self.angle_slider.setValue(int(value))
                elif key == 'spacing':
                    self.spacing_spin.setValue(value)
                elif key == 'yaw_speed':
                    self.yaw_speed_spin.setValue(value)
                elif key == 'subdivisions':
                    self.subdivision_combo.setCurrentIndex(value - 1)
                elif key == 'region_spacing':
                    self.region_spacing_spin.setValue(value)
                elif key == 'reduce_overlap':
                    self.reduce_overlap_check.setChecked(value)
                elif key == 'flight_mode':
                    index = 1 if value == 'smart_collision' else 0
                    self.flight_mode_combo.setCurrentIndex(index)
        
        logger.info("參數已設置")
    
    def reset_to_default(self):
        """重置為預設參數"""
        default_params = {
            'altitude': 50.0,
            'speed': 10.0,
            'angle': 0.0,
            'spacing': 20.0,
            'yaw_speed': 60.0,
            'subdivisions': 1,
            'region_spacing': 3.0,
            'reduce_overlap': True,
            'flight_mode': 'smart_collision'
        }
        
        self.set_parameters(default_params)
        self.parameters_changed.emit(default_params)
        logger.info("參數已重置為預設值")
