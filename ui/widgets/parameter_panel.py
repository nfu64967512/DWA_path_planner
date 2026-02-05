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

from config import get_settings
from utils.logger import get_logger

# 獲取配置和日誌實例
settings = get_settings()
logger = get_logger()


class ParameterPanel(QWidget):
    """
    參數面板
    
    提供各種飛行和測繪參數的設置
    """
    
    # 信號定義
    parameters_changed = pyqtSignal(dict)  # 參數變更信號
    corner_added = pyqtSignal(float, float)  # 新增邊界點信號
    clear_corners_requested = pyqtSignal()  # 清除邊界點信號
    open_click_map_requested = pyqtSignal()  # 打開點擊地圖視窗
    
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
            'flight_mode': 'smart_collision',
            'algorithm': 'grid',
            'vehicle_type': '多旋翼',
            'vehicle_model': 'DJI Mavic 3',
            'turn_radius': 50.0,  # 固定翼轉彎半徑
        }
        
        # 建立 UI
        self.init_ui()
        
        logger.info("參數面板初始化完成")
    
    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 邊界點管理群組（放在最上方）
        corner_group = self.create_corner_management()
        layout.addWidget(corner_group)

        # 演算法與載具選擇群組
        algo_vehicle_group = self.create_algorithm_vehicle_selection()
        layout.addWidget(algo_vehicle_group)

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
    
    def create_corner_management(self):
        """創建邊界點管理群組"""
        group = QGroupBox("邊界點管理")
        layout = QVBoxLayout(group)

        # 座標輸入區
        coord_layout = QHBoxLayout()

        # 緯度輸入
        lat_layout = QVBoxLayout()
        lat_layout.addWidget(QLabel("緯度:"))
        self.lat_input = QDoubleSpinBox()
        self.lat_input.setRange(-90.0, 90.0)
        self.lat_input.setDecimals(6)
        self.lat_input.setValue(settings.map.default_lat)
        lat_layout.addWidget(self.lat_input)
        coord_layout.addLayout(lat_layout)

        # 經度輸入
        lon_layout = QVBoxLayout()
        lon_layout.addWidget(QLabel("經度:"))
        self.lon_input = QDoubleSpinBox()
        self.lon_input.setRange(-180.0, 180.0)
        self.lon_input.setDecimals(6)
        self.lon_input.setValue(settings.map.default_lon)
        lon_layout.addWidget(self.lon_input)
        coord_layout.addLayout(lon_layout)

        layout.addLayout(coord_layout)

        # 按鈕區
        btn_layout = QHBoxLayout()

        self.add_corner_btn = QPushButton("➕ 新增角點")
        self.add_corner_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.add_corner_btn.clicked.connect(self.on_add_corner)
        btn_layout.addWidget(self.add_corner_btn)

        self.clear_corners_btn = QPushButton("🗑️ 清除全部")
        self.clear_corners_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.clear_corners_btn.clicked.connect(self.on_clear_corners)
        btn_layout.addWidget(self.clear_corners_btn)

        layout.addLayout(btn_layout)

        # 角點數量顯示
        self.corner_count_label = QLabel("目前角點: 0 個")
        self.corner_count_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        layout.addWidget(self.corner_count_label)

        # 打開點擊地圖視窗按鈕
        click_map_btn = QPushButton("🗺️ 打開點擊地圖")
        click_map_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        click_map_btn.setToolTip("打開獨立地圖視窗，左鍵點擊直接添加角點")
        click_map_btn.clicked.connect(lambda: self.open_click_map_requested.emit())
        layout.addWidget(click_map_btn)

        # 預設測試區域按鈕
        preset_btn = QPushButton("📍 快速添加測試區域")
        preset_btn.setToolTip("在預設位置添加一個 200m x 200m 的矩形區域")
        preset_btn.clicked.connect(self.on_add_preset_area)
        layout.addWidget(preset_btn)

        # 提示
        hint_label = QLabel("提示: 需要至少 3 個角點才能生成路徑")
        hint_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(hint_label)

        return group

    def create_algorithm_vehicle_selection(self):
        """創建演算法與載具選擇群組"""
        group = QGroupBox("演算法與載具")
        layout = QFormLayout(group)

        # 路徑演算法選擇
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems([
            "網格掃描 (Grid) - 覆蓋任務",
            "螺旋掃描 (Spiral) - 覆蓋任務",
            "A* 路徑規劃 - 點對點",
            "RRT 路徑規劃 - 點對點",
            "RRT* 路徑規劃 - 最優路徑",
            "Dijkstra 路徑規劃 - 最短路徑",
            "DWA 動態窗口 - 即時避障"
        ])
        self.algorithm_combo.setCurrentIndex(0)
        self.algorithm_combo.currentIndexChanged.connect(self.on_algorithm_changed)
        self.algorithm_combo.setToolTip(
            "Grid/Spiral: 適用於區域覆蓋任務\n"
            "A*/RRT/Dijkstra: 適用於點對點路徑規劃\n"
            "DWA: 適用於即時避障"
        )
        layout.addRow("路徑演算法:", self.algorithm_combo)

        # 載具類型選擇
        self.vehicle_type_combo = QComboBox()
        self.vehicle_type_combo.addItems(["多旋翼", "固定翼", "VTOL"])
        self.vehicle_type_combo.setCurrentIndex(0)
        self.vehicle_type_combo.currentIndexChanged.connect(self.on_vehicle_type_changed)
        layout.addRow("載具類型:", self.vehicle_type_combo)

        # 載具型號選擇
        self.vehicle_model_combo = QComboBox()
        self._update_vehicle_models("多旋翼")
        self.vehicle_model_combo.currentIndexChanged.connect(self.on_vehicle_model_changed)
        layout.addRow("載具型號:", self.vehicle_model_combo)

        # 載具資訊標籤
        self.vehicle_info_label = QLabel("選擇載具以顯示資訊")
        self.vehicle_info_label.setStyleSheet("color: #888; font-size: 10px;")
        self.vehicle_info_label.setWordWrap(True)
        layout.addRow("", self.vehicle_info_label)

        return group

    def _update_vehicle_models(self, vehicle_type: str):
        """更新載具型號列表"""
        self.vehicle_model_combo.clear()

        if vehicle_type == "多旋翼":
            self.vehicle_model_combo.addItems([
                "DJI Mavic 3",
                "DJI Phantom 4 Pro",
                "DJI Mini 3 Pro",
                "Generic Quadcopter"
            ])
        elif vehicle_type == "固定翼":
            self.vehicle_model_combo.addItems([
                "Generic Fixed Wing"
            ])
        elif vehicle_type == "VTOL":
            self.vehicle_model_combo.addItems([
                "Generic VTOL"
            ])

    def on_algorithm_changed(self, index):
        """處理演算法變更"""
        algorithms = ['grid', 'spiral', 'astar', 'rrt', 'rrt_star', 'dijkstra', 'dwa']
        algorithm = algorithms[index] if index < len(algorithms) else 'grid'
        self.update_parameter('algorithm', algorithm)

        # 更新主視窗的演算法設定
        main_window = self.parent()
        if main_window:
            main_window.current_algorithm = algorithm

        # 顯示演算法說明
        algorithm_info = {
            'grid': "網格掃描：適合覆蓋測繪任務，之字形路徑",
            'spiral': "螺旋掃描：從外圍向中心螺旋掃描",
            'astar': "A* 演算法：使用啟發式搜索的最短路徑",
            'rrt': "RRT 演算法：快速探索隨機樹，適合複雜環境",
            'rrt_star': "RRT* 演算法：RRT 的最優化版本",
            'dijkstra': "Dijkstra 演算法：保證最短路徑",
            'dwa': "DWA 動態窗口：即時避障，適合動態環境"
        }
        info = algorithm_info.get(algorithm, "")
        self.algorithm_combo.setToolTip(info)

        logger.info(f"演算法變更: {algorithm} - {info}")

    def on_vehicle_type_changed(self, index):
        """處理載具類型變更"""
        vehicle_types = ["多旋翼", "固定翼", "VTOL"]
        vehicle_type = vehicle_types[index] if index < len(vehicle_types) else "多旋翼"
        self._update_vehicle_models(vehicle_type)
        self.update_parameter('vehicle_type', vehicle_type)

        # 顯示/隱藏固定翼專用參數
        is_fixed_wing = (vehicle_type == "固定翼")
        if hasattr(self, 'turn_radius_spin'):
            self.turn_radius_spin.setVisible(is_fixed_wing)
            self.turn_radius_label.setVisible(is_fixed_wing)

        logger.info(f"載具類型變更: {vehicle_type}")

    def on_vehicle_model_changed(self, index):
        """處理載具型號變更"""
        model = self.vehicle_model_combo.currentText()
        self.update_parameter('vehicle_model', model)

        # 更新載具資訊
        vehicle_info = self._get_vehicle_info(model)
        self.vehicle_info_label.setText(vehicle_info)

        # 如果有對應的參數，自動更新飛行參數
        self._apply_vehicle_defaults(model)

        logger.info(f"載具型號變更: {model}")

    def _get_vehicle_info(self, model: str) -> str:
        """獲取載具資訊"""
        info_db = {
            "DJI Mavic 3": "最大速度: 19m/s | 飛行時間: 46min | 抗風: 12m/s",
            "DJI Phantom 4 Pro": "最大速度: 20m/s | 飛行時間: 30min | 抗風: 10m/s",
            "DJI Mini 3 Pro": "最大速度: 16m/s | 飛行時間: 34min | 抗風: 10.7m/s",
            "Generic Quadcopter": "最大速度: 15m/s | 飛行時間: 25min | 抗風: 10m/s",
            "Generic Fixed Wing": "最大速度: 25m/s | 飛行時間: 120min | 抗風: 15m/s",
            "Generic VTOL": "最大速度: 30m/s | 飛行時間: 90min | 抗風: 12m/s",
        }
        return info_db.get(model, "無資訊")

    def _apply_vehicle_defaults(self, model: str):
        """根據載具型號應用預設參數"""
        defaults_db = {
            "DJI Mavic 3": {'speed': 15.0, 'altitude': 60.0, 'turn_radius': 0},
            "DJI Phantom 4 Pro": {'speed': 12.0, 'altitude': 50.0, 'turn_radius': 0},
            "DJI Mini 3 Pro": {'speed': 10.0, 'altitude': 40.0, 'turn_radius': 0},
            "Generic Quadcopter": {'speed': 8.0, 'altitude': 50.0, 'turn_radius': 0},
            "Generic Fixed Wing": {'speed': 18.0, 'altitude': 100.0, 'turn_radius': 50.0},
            "Generic VTOL": {'speed': 15.0, 'altitude': 80.0, 'turn_radius': 30.0},
        }

        defaults = defaults_db.get(model)
        if defaults:
            self.speed_spin.setValue(defaults['speed'])
            self.altitude_spin.setValue(defaults['altitude'])
            if defaults.get('turn_radius', 0) > 0:
                self.turn_radius_spin.setValue(defaults['turn_radius'])

    def on_add_preset_area(self):
        """添加預設測試區域"""
        # 清除現有角點
        self.clear_corners_requested.emit()

        # 在預設位置周圍創建一個約 200m x 200m 的矩形
        center_lat = settings.map.default_lat
        center_lon = settings.map.default_lon

        # 大約 0.0018 度 ≈ 200m
        offset = 0.0009

        corners = [
            (center_lat + offset, center_lon - offset),  # 左上
            (center_lat + offset, center_lon + offset),  # 右上
            (center_lat - offset, center_lon + offset),  # 右下
            (center_lat - offset, center_lon - offset),  # 左下
        ]

        for lat, lon in corners:
            self.corner_added.emit(lat, lon)

        logger.info("已添加預設測試區域（4個角點）")

    def on_add_corner(self):
        """新增角點"""
        lat = self.lat_input.value()
        lon = self.lon_input.value()
        self.corner_added.emit(lat, lon)
        logger.info(f"手動新增角點: ({lat:.6f}, {lon:.6f})")

    def on_clear_corners(self):
        """清除所有角點"""
        self.clear_corners_requested.emit()
        logger.info("請求清除所有角點")

    def update_corner_count(self, count: int):
        """更新角點數量顯示"""
        self.corner_count_label.setText(f"目前角點: {count} 個")
        if count >= 3:
            self.corner_count_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.corner_count_label.setStyleSheet("color: #f44336; font-weight: bold;")

    def create_flight_parameters(self):
        """創建飛行參數群組"""
        group = QGroupBox("飛行參數")
        layout = QFormLayout(group)
        
        # 飛行高度
        self.altitude_spin = QDoubleSpinBox()
        self.altitude_spin.setRange(settings.safety.min_altitude_m, 
                                settings.safety.max_altitude_m)
        self.altitude_spin.setValue(self.parameters['altitude'])
        self.altitude_spin.setSuffix(" m")
        self.altitude_spin.setDecimals(1)
        self.altitude_spin.valueChanged.connect(lambda v: self.update_parameter('altitude', v))
        layout.addRow("飛行高度:", self.altitude_spin)
        
        # 飛行速度
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(settings.safety.min_speed_mps, 
                                settings.safety.max_speed_mps)
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

        # 固定翼轉彎半徑（預設隱藏）
        self.turn_radius_label = QLabel("轉彎半徑:")
        self.turn_radius_spin = QDoubleSpinBox()
        self.turn_radius_spin.setRange(10.0, 500.0)
        self.turn_radius_spin.setValue(self.parameters['turn_radius'])
        self.turn_radius_spin.setSuffix(" m")
        self.turn_radius_spin.setDecimals(1)
        self.turn_radius_spin.setToolTip("固定翼飛機的最小轉彎半徑，用於生成平滑路徑")
        self.turn_radius_spin.valueChanged.connect(lambda v: self.update_parameter('turn_radius', v))
        layout.addRow(self.turn_radius_label, self.turn_radius_spin)

        # 預設隱藏固定翼參數
        self.turn_radius_label.setVisible(False)
        self.turn_radius_spin.setVisible(False)

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
        self.spacing_spin.setRange(settings.safety.min_spacing_m, 
                                settings.safety.max_spacing_m)
        self.spacing_spin.setValue(self.parameters['spacing'])
        self.spacing_spin.setSuffix(" m")
        self.spacing_spin.setDecimals(1)
        self.spacing_spin.valueChanged.connect(lambda v: self.update_parameter('spacing', v))
        layout.addRow("航線間距:", self.spacing_spin)
        
        # 子區域分割
        self.subdivision_combo = QComboBox()
        self.subdivision_combo.addItems([
            "1 (不分割)", 
            "2 區域", 
            "3 區域", 
            "4 區域 (2x2)", 
            "5 區域",
            "6 區域 (2x3)"
        ])
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
        safety_label = QLabel(f"{settings.safety.default_safety_distance_m} m")
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
                elif key == 'turn_radius':
                    self.turn_radius_spin.setValue(value)

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
            'flight_mode': 'smart_collision',
            'turn_radius': 50.0,
        }

        self.set_parameters(default_params)
        self.parameters_changed.emit(default_params)
        logger.info("參數已重置為預設值")
