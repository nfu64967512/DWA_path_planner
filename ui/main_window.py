"""
主視窗模組
整合地圖、參數面板、任務面板等核心 UI 組件
"""

import sys
import math
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QToolBar, QMessageBox,
    QFileDialog, QLabel
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QShortcut

# 修正導入路徑
from config import get_settings
from utils.logger import get_logger
from utils.file_io import write_waypoints, create_waypoint_line
from mission import MissionManager
from core.global_planner.coverage_planner import CoveragePlanner, CoverageParameters, ScanPattern
from core.global_planner.astar import AStarPlanner
from core.global_planner.rrt import RRTPlanner, RRTStarPlanner
from core.collision import CollisionChecker

# 獲取配置和日誌實例
settings = get_settings()
logger = get_logger()

# 常數定義
MIN_CORNERS = 3  # 最少邊界點數量
MAX_CORNERS = 100  # 最大邊界點數量


class MainWindow(QMainWindow):
    """
    主視窗類
    
    整合地圖顯示、參數控制、任務管理等核心功能
    """
    
    # 信號定義
    mission_changed = pyqtSignal(object)  # 任務變更信號
    waypoints_updated = pyqtSignal(list)  # 航點更新信號
    
    def __init__(self):
        """初始化主視窗"""
        super().__init__()
        
        # 視窗基本設置（使用 settings 替代 Config）
        self.setWindowTitle(settings.ui.window_title)
        self.setGeometry(100, 100, settings.ui.window_width, settings.ui.window_height)
        self.setMinimumSize(settings.ui.min_window_width, settings.ui.min_window_height)
        
        # 初始化核心組件
        self.mission_manager = MissionManager()
        
        # 初始化變數
        self.init_variables()
        
        # 建立 UI
        self.init_ui()
        
        # 載入樣式表
        self.load_stylesheet()
        
        # 顯示歡迎信息
        self.statusBar().showMessage("無人機路徑規劃工具已就緒", 5000)
        
        logger.info("主視窗初始化完成")
    
    def init_variables(self):
        """初始化變數"""
        self.current_mission = None
        self.corners = []  # 邊界點
        self.waypoints = []  # 航點
        self.obstacles = []  # 障礙物

        # 當前演算法
        self.current_algorithm = 'grid'

        # 當前載具設定
        self.current_vehicle_type = '多旋翼'
        self.current_vehicle_model = 'DJI Mavic 3'

        # 飛行參數
        self.flight_params = {
            'altitude': 50.0,
            'speed': 10.0,
            'angle': 0.0,
            'spacing': 20.0,
            'yaw_speed': 60.0,
            'subdivisions': 1,
            'region_spacing': 3.0,
            'turn_radius': 50.0,  # 固定翼轉彎半徑 (m)
        }

        # 即時路徑生成設定
        self.auto_generate_path = True  # 是否自動生成路徑
        self.path_generation_timer = None  # 延遲生成計時器
        self.path_generation_delay = 300  # 延遲時間 (ms)
    
    def init_ui(self):
        """初始化 UI 組件"""
        # 創建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主佈局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 創建分割器（地圖 | 控制面板）
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左側：地圖區域
        self.map_widget = self.create_map_widget()
        splitter.addWidget(self.map_widget)
        
        # 右側：控制面板
        control_panel = self.create_control_panel()
        splitter.addWidget(control_panel)
        
        # 設置分割比例（55% 地圖，45% 控制面板）- 更平衡的佈局
        splitter.setStretchFactor(0, 55)
        splitter.setStretchFactor(1, 45)
        splitter.setSizes([700, 500])  # 初始大小
        
        main_layout.addWidget(splitter)
        
        # 創建工具列
        self.create_toolbar()
        
        # 創建狀態列
        self.create_statusbar()
        
        # 創建選單
        self.create_menus()

        # 設置快捷鍵
        self.setup_shortcuts()
    
    def create_map_widget(self):
        """創建地圖組件"""
        from ui.widgets.map_widget import MapWidget

        map_widget = MapWidget(self)

        # 連接信號
        map_widget.corner_added.connect(self.on_corner_added)
        map_widget.corner_moved.connect(self.on_corner_moved)

        return map_widget

    def open_click_map_window(self):
        """打開可點擊的地圖視窗（使用 tkintermapview）"""
        try:
            import tkinter as tk
            import tkintermapview

            # 創建 Tkinter 視窗
            self.tk_map_window = tk.Toplevel()
            self.tk_map_window.title("點擊地圖添加角點 - 左鍵點擊添加")
            self.tk_map_window.geometry("900x700")

            # 創建地圖
            map_widget = tkintermapview.TkinterMapView(
                self.tk_map_window,
                width=900,
                height=650,
                corner_radius=0
            )
            map_widget.pack(fill="both", expand=True)

            # 設置位置
            map_widget.set_position(
                settings.map.default_lat,
                settings.map.default_lon
            )
            map_widget.set_zoom(settings.map.default_zoom)

            # 嘗試設置 Google 衛星圖
            try:
                map_widget.set_tile_server(
                    "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                    max_zoom=20
                )
            except:
                pass

            # 儲存標記列表
            self.tk_markers = []
            self.tk_polygon = None

            def on_click(coords):
                lat, lon = coords
                # 添加標記
                point_num = len(self.corners) + 1
                marker = map_widget.set_marker(
                    lat, lon,
                    text=f"P{point_num}",
                    marker_color_circle="green"
                )
                self.tk_markers.append(marker)

                # 添加到主視窗
                self.on_manual_corner_added(lat, lon)

                # 更新多邊形
                if len(self.corners) >= 3:
                    if hasattr(self, 'tk_polygon') and self.tk_polygon:
                        self.tk_polygon.delete()
                    self.tk_polygon = map_widget.set_polygon(
                        self.corners,
                        fill_color="green",
                        outline_color="darkgreen",
                        border_width=2
                    )

                logger.info(f"Tkinter 地圖點擊: ({lat:.6f}, {lon:.6f})")

            map_widget.add_left_click_map_command(on_click)

            # 添加說明標籤
            info_frame = tk.Frame(self.tk_map_window)
            info_frame.pack(fill="x", pady=5)
            tk.Label(
                info_frame,
                text="左鍵點擊地圖添加角點 | 滾輪縮放 | 右鍵拖曳移動",
                font=("Arial", 10)
            ).pack()

            logger.info("已打開 Tkinter 地圖視窗")

        except ImportError:
            QMessageBox.warning(
                self, "缺少套件",
                "請先安裝 tkintermapview:\n\npip install tkintermapview"
            )
        except Exception as e:
            logger.error(f"打開 Tkinter 地圖失敗: {e}")
            QMessageBox.critical(self, "錯誤", f"打開地圖視窗失敗:\n{str(e)}")
    
    def create_control_panel(self):
        """創建控制面板"""
        from ui.widgets.parameter_panel import ParameterPanel
        from ui.widgets.mission_panel import MissionPanel
        
        # 創建容器
        panel_widget = QWidget()
        panel_layout = QVBoxLayout(panel_widget)
        panel_layout.setContentsMargins(5, 5, 5, 5)
        panel_layout.setSpacing(10)
        
        # 參數面板
        self.parameter_panel = ParameterPanel(self)
        # 連接參數面板的邊界點信號
        self.parameter_panel.corner_added.connect(self.on_manual_corner_added)
        self.parameter_panel.clear_corners_requested.connect(self.on_clear_corners)
        self.parameter_panel.open_click_map_requested.connect(self.open_click_map_window)
        panel_layout.addWidget(self.parameter_panel)

        # 任務面板
        self.mission_panel = MissionPanel(self)
        panel_layout.addWidget(self.mission_panel)
        
        # 添加彈性空間
        panel_layout.addStretch()
        
        # 連接信號
        self.parameter_panel.parameters_changed.connect(self.on_parameters_changed)
        self.mission_panel.preview_requested.connect(self.on_preview_paths)
        self.mission_panel.export_requested.connect(self.on_export_waypoints)
        self.mission_panel.clear_requested.connect(self.on_clear_all)
        
        return panel_widget
    
    def create_toolbar(self):
        """創建工具列"""
        toolbar = QToolBar("主工具列")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # 新建任務
        new_action = QAction("🆕 新建", self)
        new_action.setStatusTip("創建新任務")
        new_action.triggered.connect(self.on_new_mission)
        toolbar.addAction(new_action)
        
        # 開啟任務
        open_action = QAction("📂 開啟", self)
        open_action.setStatusTip("開啟現有任務")
        open_action.triggered.connect(self.on_open_mission)
        toolbar.addAction(open_action)
        
        # 儲存任務
        save_action = QAction("💾 儲存", self)
        save_action.setStatusTip("儲存當前任務")
        save_action.triggered.connect(self.on_save_mission)
        toolbar.addAction(save_action)
        
        toolbar.addSeparator()
        
        # 預覽路徑
        preview_action = QAction("👁 預覽", self)
        preview_action.setStatusTip("預覽飛行路徑")
        preview_action.triggered.connect(self.on_preview_paths)
        toolbar.addAction(preview_action)
        
        # 匯出航點
        export_action = QAction("📤 匯出", self)
        export_action.setStatusTip("匯出航點檔案")
        export_action.triggered.connect(self.on_export_waypoints)
        toolbar.addAction(export_action)
        
        toolbar.addSeparator()
        
        # 清除全部
        clear_action = QAction("🗑 清除", self)
        clear_action.setStatusTip("清除所有標記和路徑")
        clear_action.triggered.connect(self.on_clear_all)
        toolbar.addAction(clear_action)
    
    def create_statusbar(self):
        """創建狀態列"""
        statusbar = QStatusBar()
        self.setStatusBar(statusbar)
        
        # 添加永久顯示的資訊
        self.coord_label = QLabel("座標: --")
        statusbar.addPermanentWidget(self.coord_label)
        
        self.waypoint_label = QLabel("航點: 0")
        statusbar.addPermanentWidget(self.waypoint_label)
        
        self.distance_label = QLabel("距離: 0.0m")
        statusbar.addPermanentWidget(self.distance_label)
    
    def create_menus(self):
        """創建選單列（PyQt6 兼容版本）"""
        menubar = self.menuBar()
        
        # === 檔案選單 ===
        file_menu = menubar.addMenu("檔案(&F)")
        
        action = file_menu.addAction("新建任務")
        action.setShortcut(QKeySequence("Ctrl+N"))
        action.triggered.connect(self.on_new_mission)
        
        action = file_menu.addAction("開啟任務")
        action.setShortcut(QKeySequence("Ctrl+O"))
        action.triggered.connect(self.on_open_mission)
        
        action = file_menu.addAction("儲存任務")
        action.setShortcut(QKeySequence("Ctrl+S"))
        action.triggered.connect(self.on_save_mission)
        
        file_menu.addSeparator()
        
        action = file_menu.addAction("匯出航點")
        action.setShortcut(QKeySequence("Ctrl+E"))
        action.triggered.connect(self.on_export_waypoints)
        
        file_menu.addSeparator()
        
        action = file_menu.addAction("退出")
        action.setShortcut(QKeySequence("Ctrl+Q"))
        action.triggered.connect(self.close)
        
        # === 編輯選單 ===
        edit_menu = menubar.addMenu("編輯(&E)")
        
        action = edit_menu.addAction("清除路徑")
        action.triggered.connect(self.on_clear_paths)
        
        action = edit_menu.addAction("清除邊界")
        action.triggered.connect(self.on_clear_corners)
        
        action = edit_menu.addAction("清除全部")
        action.setShortcut(QKeySequence("Ctrl+R"))
        action.triggered.connect(self.on_clear_all)
        
        # === 檢視選單 ===
        view_menu = menubar.addMenu("檢視(&V)")
        
        action = view_menu.addAction("重置視圖")
        action.triggered.connect(self.on_reset_view)
        
        action = view_menu.addAction("顯示網格")
        action.triggered.connect(self.on_toggle_grid)
        
        # === 工具選單 ===
        tools_menu = menubar.addMenu("工具(&T)")

        action = tools_menu.addAction("🗺️ 多邊形編輯器")
        action.setShortcut(QKeySequence("Ctrl+M"))
        action.triggered.connect(self.on_open_polygon_editor)

        action = tools_menu.addAction("🖱️ 點擊地圖視窗 (Tkinter)")
        action.triggered.connect(self.open_click_map_window)

        tools_menu.addSeparator()

        action = tools_menu.addAction("相機配置")
        action.triggered.connect(self.on_camera_config)

        action = tools_menu.addAction("飛行器配置")
        action.triggered.connect(self.on_vehicle_config)

        tools_menu.addSeparator()

        action = tools_menu.addAction("障礙物管理")
        action.triggered.connect(self.on_obstacle_manager)
        
        # === 說明選單 ===
        help_menu = menubar.addMenu("說明(&H)")
        
        action = help_menu.addAction("使用說明")
        action.triggered.connect(self.on_show_help)
        
        action = help_menu.addAction("關於")
        action.triggered.connect(self.on_about)
    
    def setup_shortcuts(self):
        """設置快捷鍵"""
        # Enter 鍵 - 生成路徑
        enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        enter_shortcut.activated.connect(self.on_preview_paths)

        # 也支援小鍵盤的 Enter
        enter_shortcut2 = QShortcut(QKeySequence(Qt.Key.Key_Enter), self)
        enter_shortcut2.activated.connect(self.on_preview_paths)

        # Space 鍵 - 也可以生成路徑（備選）
        space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space_shortcut.activated.connect(self.on_preview_paths)

        # Escape 鍵 - 清除路徑
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(self.on_clear_paths)

        # Delete 鍵 - 刪除最後一個角點
        del_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        del_shortcut.activated.connect(self.on_delete_last_corner)

        # Backspace 鍵 - 也可以刪除最後一個角點
        backspace_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self)
        backspace_shortcut.activated.connect(self.on_delete_last_corner)

        logger.info("快捷鍵設置完成: Enter=生成路徑, Delete=刪除角點, Esc=清除路徑")

    def on_delete_last_corner(self):
        """刪除最後一個角點"""
        if self.corners:
            removed = self.corners.pop()
            # 同步到地圖
            if self.map_widget.corners:
                self.map_widget.corners.pop()
                self.map_widget.markers.pop() if self.map_widget.markers else None
            # 重新渲染地圖
            self.map_widget.init_map()
            for lat, lon in self.corners:
                self.map_widget.add_corner(lat, lon)
            # 更新 UI
            self.parameter_panel.update_corner_count(len(self.corners))
            self.update_statusbar()
            logger.info(f"刪除角點: ({removed[0]:.6f}, {removed[1]:.6f}), 剩餘 {len(self.corners)} 個")

            # 如果啟用自動生成，觸發路徑更新
            if self.auto_generate_path and len(self.corners) >= MIN_CORNERS:
                self._schedule_path_generation()

    def _schedule_path_generation(self):
        """排程延遲路徑生成（防止頻繁更新）"""
        if self.path_generation_timer:
            self.path_generation_timer.stop()

        self.path_generation_timer = QTimer()
        self.path_generation_timer.setSingleShot(True)
        self.path_generation_timer.timeout.connect(self._auto_generate_path)
        self.path_generation_timer.start(self.path_generation_delay)

    def _auto_generate_path(self):
        """自動生成路徑（靜默模式，不顯示對話框）"""
        if len(self.corners) < MIN_CORNERS:
            return

        try:
            # 使用 CoveragePlanner 生成路徑
            planner = CoveragePlanner()

            # 獲取當前選擇的演算法模式
            algorithm = getattr(self, 'current_algorithm', 'grid')
            if algorithm == 'grid':
                pattern = ScanPattern.GRID
            elif algorithm == 'spiral':
                pattern = ScanPattern.SPIRAL
            else:
                pattern = ScanPattern.GRID

            # 判斷是否為固定翼
            is_fixed_wing = self.current_vehicle_type == '固定翼'

            # 建立覆蓋參數
            params = CoverageParameters(
                spacing=self.flight_params['spacing'],
                angle=self.flight_params['angle'],
                pattern=pattern,
                is_fixed_wing=is_fixed_wing,
                turn_radius=self.flight_params.get('turn_radius', 50.0),
                smooth_turns=is_fixed_wing
            )

            # 生成覆蓋路徑
            path = planner.plan_coverage(self.corners, params)

            if not path:
                return

            # 計算總飛行距離
            total_distance = 0.0
            for i in range(len(path) - 1):
                lat1, lon1 = path[i]
                lat2, lon2 = path[i + 1]
                dlat = (lat2 - lat1) * 111111.0
                dlon = (lon2 - lon1) * 111111.0 * math.cos(math.radians((lat1 + lat2) / 2))
                total_distance += math.sqrt(dlat**2 + dlon**2)

            # 儲存航點
            self.waypoints = path

            # 在地圖上顯示路徑
            self.map_widget.display_path(path, self.flight_params['altitude'])

            # 更新狀態列
            self.waypoint_label.setText(f"航點: {len(path)}")
            self.distance_label.setText(f"距離: {total_distance:.0f}m")

            self.statusBar().showMessage(f"即時生成: {len(path)} 個航點, {total_distance:.0f}m", 2000)
            logger.info(f"即時路徑生成: {len(path)} 個航點")

        except Exception as e:
            logger.error(f"即時路徑生成失敗: {e}")

    def load_stylesheet(self):
        """載入樣式表"""
        try:
            from pathlib import Path
            style_path = Path(__file__).parent / "resources" / "styles" / "dark_theme.qss"

            if style_path.exists():
                with open(style_path, 'r', encoding='utf-8') as f:
                    self.setStyleSheet(f.read())
                logger.info("樣式表載入成功")
            else:
                logger.warning(f"樣式表不存在: {style_path}")
        except Exception as e:
            logger.error(f"載入樣式表失敗: {e}")
    
    # ==========================================
    # 信號處理函數
    # ==========================================
    
    def on_corner_added(self, lat, lon):
        """處理新增邊界點（從地圖點擊）"""
        # 檢查是否超過最大數量
        if len(self.corners) >= MAX_CORNERS:
            QMessageBox.warning(
                self, "已達上限",
                f"已達到最大邊界點數量 ({MAX_CORNERS} 個)！"
            )
            return

        self.corners.append((lat, lon))
        remaining = MAX_CORNERS - len(self.corners)
        logger.info(f"新增邊界點 #{len(self.corners)}: ({lat:.6f}, {lon:.6f}) [剩餘: {remaining}]")
        self.parameter_panel.update_corner_count(len(self.corners))
        self.update_statusbar()

        # 如果啟用自動生成，觸發路徑更新
        if self.auto_generate_path and len(self.corners) >= MIN_CORNERS:
            self._schedule_path_generation()

    def on_manual_corner_added(self, lat, lon):
        """處理手動新增邊界點（從參數面板）"""
        # 檢查是否超過最大數量
        if len(self.corners) >= MAX_CORNERS:
            QMessageBox.warning(
                self, "已達上限",
                f"已達到最大邊界點數量 ({MAX_CORNERS} 個)！"
            )
            return

        self.corners.append((lat, lon))
        # 在地圖上添加標記
        self.map_widget.add_corner(lat, lon)
        remaining = MAX_CORNERS - len(self.corners)
        logger.info(f"手動新增邊界點 #{len(self.corners)}: ({lat:.6f}, {lon:.6f}) [剩餘: {remaining}]")
        self.parameter_panel.update_corner_count(len(self.corners))
        self.update_statusbar()

        # 如果啟用自動生成，觸發路徑更新
        if self.auto_generate_path and len(self.corners) >= MIN_CORNERS:
            self._schedule_path_generation()
    
    def on_corner_moved(self, index, lat, lon):
        """處理移動邊界點"""
        if 0 <= index < len(self.corners):
            self.corners[index] = (lat, lon)
            logger.info(f"移動邊界點 #{index+1}: ({lat:.6f}, {lon:.6f})")
            self.update_statusbar()
    
    def on_parameters_changed(self, params):
        """處理參數變更"""
        # 處理演算法變更
        if 'algorithm' in params:
            self.current_algorithm = params['algorithm']
            logger.info(f"演算法變更: {self.current_algorithm}")

        # 處理載具變更
        if 'vehicle_type' in params:
            self.current_vehicle_type = params['vehicle_type']
        if 'vehicle_model' in params:
            self.current_vehicle_model = params['vehicle_model']

        # 更新飛行參數
        flight_keys = ['altitude', 'speed', 'angle', 'spacing', 'yaw_speed', 'subdivisions', 'region_spacing']
        for key in flight_keys:
            if key in params:
                self.flight_params[key] = params[key]

        logger.info(f"參數已更新: {params}")
    
    def on_preview_paths(self):
        """預覽飛行路徑"""
        if len(self.corners) < MIN_CORNERS:
            QMessageBox.warning(
                self, "邊界不足",
                f"需要至少 {MIN_CORNERS} 個邊界點才能生成路徑"
            )
            return

        try:
            # 獲取當前選擇的演算法
            algorithm = getattr(self, 'current_algorithm', 'grid')

            # 判斷是否為固定翼
            is_fixed_wing = self.current_vehicle_type == '固定翼'

            path = None

            # 根據演算法類型生成路徑
            if algorithm in ['grid', 'spiral']:
                # 覆蓋路徑規劃（Grid/Spiral）
                planner = CoveragePlanner()
                pattern = ScanPattern.GRID if algorithm == 'grid' else ScanPattern.SPIRAL

                params = CoverageParameters(
                    spacing=self.flight_params['spacing'],
                    angle=self.flight_params['angle'],
                    pattern=pattern,
                    is_fixed_wing=is_fixed_wing,
                    turn_radius=self.flight_params.get('turn_radius', 50.0),
                    smooth_turns=is_fixed_wing
                )

                path = planner.plan_coverage(self.corners, params)

            elif algorithm == 'astar':
                # A* 路徑規劃（點對點）
                if len(self.corners) >= 2:
                    astar_planner = AStarPlanner(
                        collision_checker=None,
                        step_size=self.flight_params['spacing'],
                        heuristic='euclidean'
                    )
                    path = astar_planner.plan(
                        start=self.corners[0],
                        goal=self.corners[-1],
                        boundary=self.corners
                    )

            elif algorithm in ['rrt', 'rrt_star']:
                # RRT/RRT* 路徑規劃
                if len(self.corners) >= 2:
                    # 計算搜索區域
                    lats = [c[0] for c in self.corners]
                    lons = [c[1] for c in self.corners]
                    search_area = (min(lats), min(lons), max(lats), max(lons))

                    # 創建空的碰撞檢測器（無障礙物）
                    collision_checker = CollisionChecker()

                    if algorithm == 'rrt':
                        rrt_planner = RRTPlanner(
                            collision_checker=collision_checker,
                            step_size=0.0001,  # 經緯度單位
                            goal_sample_rate=0.1,
                            max_iter=1000
                        )
                    else:
                        rrt_planner = RRTStarPlanner(
                            collision_checker=collision_checker,
                            step_size=0.0001,
                            goal_sample_rate=0.1,
                            max_iter=1000,
                            search_radius=0.0005
                        )

                    path = rrt_planner.plan(
                        start=self.corners[0],
                        goal=self.corners[-1],
                        search_area=search_area
                    )

            elif algorithm == 'dijkstra':
                # Dijkstra 使用與 A* 相同的邏輯
                if len(self.corners) >= 2:
                    astar_planner = AStarPlanner(
                        collision_checker=None,
                        step_size=self.flight_params['spacing'],
                        heuristic='euclidean',
                        heuristic_weight=0.0  # weight=0 等同於 Dijkstra
                    )
                    path = astar_planner.plan(
                        start=self.corners[0],
                        goal=self.corners[-1],
                        boundary=self.corners
                    )

            elif algorithm == 'dwa':
                # DWA 需要即時規劃，這裡生成直線路徑作為全域參考
                QMessageBox.information(
                    self, "DWA 演算法",
                    "DWA (動態窗口) 是局域即時規劃演算法，\n"
                    "需要配合飛行控制器使用。\n\n"
                    "目前生成直線路徑作為參考。"
                )
                path = self.corners.copy()

            else:
                # 預設使用 Grid
                planner = CoveragePlanner()
                params = CoverageParameters(
                    spacing=self.flight_params['spacing'],
                    angle=self.flight_params['angle'],
                    pattern=ScanPattern.GRID
                )
                path = planner.plan_coverage(self.corners, params)

            if not path:
                QMessageBox.warning(self, "路徑生成失敗", "無法生成覆蓋路徑，請檢查邊界點設定")
                return

            # 計算統計資訊（使用 CoveragePlanner 工具函數）
            coverage_planner = CoveragePlanner()
            area = coverage_planner.calculate_coverage_area(self.corners)
            mission_time = coverage_planner.estimate_mission_time(path, self.flight_params['speed'])

            # 計算總飛行距離
            total_distance = 0.0
            for i in range(len(path) - 1):
                lat1, lon1 = path[i]
                lat2, lon2 = path[i + 1]
                dlat = (lat2 - lat1) * 111111.0
                dlon = (lon2 - lon1) * 111111.0 * math.cos(math.radians((lat1 + lat2) / 2))
                total_distance += math.sqrt(dlat**2 + dlon**2)

            # 儲存航點
            self.waypoints = path

            # 在地圖上顯示路徑
            self.map_widget.display_path(path, self.flight_params['altitude'])

            # 更新狀態列
            self.waypoint_label.setText(f"航點: {len(path)}")
            self.distance_label.setText(f"距離: {total_distance:.0f}m")

            # 顯示結果
            QMessageBox.information(
                self, "路徑生成完成",
                f"覆蓋路徑已生成！\n\n"
                f"邊界點: {len(self.corners)} 個\n"
                f"航點數: {len(path)} 個\n"
                f"覆蓋面積: {area:.0f} m²\n"
                f"總飛行距離: {total_distance:.0f} m\n"
                f"預估飛行時間: {mission_time/60:.1f} 分鐘\n\n"
                f"參數:\n"
                f"  高度: {self.flight_params['altitude']} m\n"
                f"  速度: {self.flight_params['speed']} m/s\n"
                f"  間距: {self.flight_params['spacing']} m\n"
                f"  角度: {self.flight_params['angle']}°\n"
                f"  演算法: {algorithm}"
            )

            self.statusBar().showMessage(f"路徑生成完成：{len(path)} 個航點", 5000)
            logger.info(f"路徑生成完成：{len(path)} 個航點，距離 {total_distance:.0f}m")

        except Exception as e:
            logger.error(f"預覽失敗: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "預覽錯誤", f"生成路徑時發生錯誤：\n{str(e)}")
    
    def on_export_waypoints(self):
        """匯出航點"""
        if not self.waypoints:
            QMessageBox.warning(self, "無資料", "請先設定邊界點並預覽路徑生成航點")
            return

        # 開啟匯出對話框
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self, "儲存航點檔案",
            "",
            "QGC Waypoint Files (*.waypoints);;CSV Files (*.csv);;All Files (*)"
        )

        if filepath:
            try:
                altitude = self.flight_params['altitude']
                speed = self.flight_params['speed']

                if selected_filter == "CSV Files (*.csv)" or filepath.endswith('.csv'):
                    # 匯出為 CSV 格式
                    if not filepath.endswith('.csv'):
                        filepath += '.csv'

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write("sequence,latitude,longitude,altitude,speed\n")
                        for i, (lat, lon) in enumerate(self.waypoints):
                            f.write(f"{i},{lat:.8f},{lon:.8f},{altitude:.1f},{speed:.1f}\n")

                else:
                    # 匯出為 QGC WPL 110 格式
                    if not filepath.endswith('.waypoints'):
                        filepath += '.waypoints'

                    waypoint_lines = ['QGC WPL 110']

                    # HOME 點 (seq=0)
                    home_lat, home_lon = self.waypoints[0]
                    waypoint_lines.append(create_waypoint_line(
                        seq=0, command=16,  # MAV_CMD_NAV_WAYPOINT
                        lat=home_lat, lon=home_lon, alt=0.0,
                        current=1, autocontinue=1
                    ))

                    # 起飛點 (seq=1)
                    waypoint_lines.append(create_waypoint_line(
                        seq=1, command=22,  # MAV_CMD_NAV_TAKEOFF
                        lat=home_lat, lon=home_lon, alt=altitude,
                        param1=15.0,  # pitch
                        current=0, autocontinue=1
                    ))

                    # 航點
                    for i, (lat, lon) in enumerate(self.waypoints, start=2):
                        waypoint_lines.append(create_waypoint_line(
                            seq=i, command=16,  # MAV_CMD_NAV_WAYPOINT
                            lat=lat, lon=lon, alt=altitude,
                            param1=0.0,  # hold time
                            param2=2.0,  # acceptance radius
                            current=0, autocontinue=1
                        ))

                    # 返航點
                    waypoint_lines.append(create_waypoint_line(
                        seq=len(self.waypoints) + 2, command=20,  # MAV_CMD_NAV_RETURN_TO_LAUNCH
                        current=0, autocontinue=1
                    ))

                    write_waypoints(filepath, waypoint_lines)

                QMessageBox.information(
                    self, "匯出成功",
                    f"航點檔案已匯出！\n\n"
                    f"檔案：{filepath}\n"
                    f"航點數：{len(self.waypoints)}"
                )
                self.statusBar().showMessage(f"已匯出 {len(self.waypoints)} 個航點", 5000)
                logger.info(f"匯出航點: {filepath}")

            except Exception as e:
                logger.error(f"匯出失敗: {e}")
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "匯出錯誤", f"匯出時發生錯誤：\n{str(e)}")
    
    def on_new_mission(self):
        """創建新任務"""
        # 如果有未儲存的變更，詢問是否儲存
        if self.current_mission and self.has_unsaved_changes():
            reply = QMessageBox.question(
                self, "未儲存的變更",
                "當前任務有未儲存的變更，是否儲存？",
                QMessageBox.StandardButton.Yes | 
                QMessageBox.StandardButton.No | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.on_save_mission()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        # 清除當前任務
        self.on_clear_all_silent()
        
        # 創建新任務
        self.current_mission = self.mission_manager.create_mission("新任務")
        
        self.statusBar().showMessage("已創建新任務", 3000)
        logger.info("創建新任務")
    
    def on_open_mission(self):
        """開啟任務"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "開啟任務檔案",
            "",
            "Mission Files (*.json);;All Files (*)"
        )
        
        if filepath:
            try:
                mission = self.mission_manager.load_mission(filepath)
                self.current_mission = mission
                
                # TODO: 載入任務參數到 UI
                
                self.statusBar().showMessage(f"已載入任務：{mission.name}", 3000)
                logger.info(f"載入任務: {filepath}")
                
            except Exception as e:
                logger.error(f"載入任務失敗: {e}")
                QMessageBox.critical(self, "載入錯誤", f"載入任務時發生錯誤：\n{str(e)}")
    
    def on_save_mission(self):
        """儲存任務"""
        if not self.current_mission:
            QMessageBox.warning(self, "無任務", "沒有任務可儲存")
            return
        
        try:
            filepath = self.mission_manager.save_mission(self.current_mission)
            
            if filepath:
                self.statusBar().showMessage(f"任務已儲存", 3000)
                logger.info(f"儲存任務: {filepath}")
            else:
                QMessageBox.warning(self, "儲存失敗", "無法儲存任務")
                
        except Exception as e:
            logger.error(f"儲存任務失敗: {e}")
            QMessageBox.critical(self, "儲存錯誤", f"儲存時發生錯誤：\n{str(e)}")
    
    def on_clear_paths(self):
        """清除路徑"""
        self.map_widget.clear_paths()
        self.waypoints.clear()
        self.waypoint_label.setText("航點: 0")
        self.distance_label.setText("距離: 0.0m")
        logger.info("已清除路徑")
    
    def on_clear_corners(self):
        """清除邊界"""
        self.map_widget.clear_corners()
        self.corners.clear()
        self.parameter_panel.update_corner_count(0)
        logger.info("已清除邊界")
    
    def on_clear_all(self):
        """清除全部（帶確認）"""
        reply = QMessageBox.question(
            self, "確認清除",
            "確定要清除所有標記和路徑嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.on_clear_all_silent()
    
    def on_clear_all_silent(self):
        """清除全部（不帶確認）"""
        self.on_clear_corners()
        self.on_clear_paths()
        self.obstacles.clear()
        logger.info("已清除全部")
    
    def on_reset_view(self):
        """重置視圖"""
        self.map_widget.reset_view()
    
    def on_toggle_grid(self):
        """切換網格顯示"""
        # TODO: 實現網格顯示切換
        QMessageBox.information(self, "網格顯示", "網格顯示功能開發中")
    
    def on_camera_config(self):
        """相機配置"""
        try:
            from ui.dialogs.camera_config import CameraConfigDialog
            dialog = CameraConfigDialog(self)
            dialog.exec()
        except ImportError:
            QMessageBox.information(self, "相機配置", "相機配置功能開發中")
    
    def on_vehicle_config(self):
        """飛行器配置"""
        try:
            from ui.dialogs.vehicle_config import VehicleConfigDialog
            dialog = VehicleConfigDialog(self)
            dialog.exec()
        except ImportError:
            QMessageBox.information(self, "飛行器配置", "飛行器配置功能開發中")
    
    def on_obstacle_manager(self):
        """障礙物管理"""
        try:
            from ui.dialogs.obstacle_manager import ObstacleManagerDialog

            dialog = ObstacleManagerDialog(self, self.obstacles)
            dialog.obstacles_changed.connect(self.on_obstacles_changed)
            dialog.exec()

        except ImportError as e:
            logger.error(f"無法載入障礙物管理對話框: {e}")
            QMessageBox.warning(self, "載入失敗", "無法載入障礙物管理功能")

    def on_open_polygon_editor(self):
        """開啟多邊形編輯器"""
        try:
            from ui.widgets.polygon_editor import PolygonEditorWindow

            # 創建編輯器視窗
            self.polygon_editor_window = PolygonEditorWindow(max_corners=MAX_CORNERS)

            # 如果已有角點，載入到編輯器
            if self.corners:
                self.polygon_editor_window.editor.set_corners(self.corners)

            # 連接信號 - 當編輯完成時同步角點
            self.polygon_editor_window.polygon_completed.connect(self._on_polygon_editor_completed)
            self.polygon_editor_window.editor.corners_changed.connect(self._on_polygon_editor_corners_changed)

            self.polygon_editor_window.show()
            logger.info("已開啟多邊形編輯器")

        except Exception as e:
            logger.error(f"開啟多邊形編輯器失敗: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "錯誤", f"無法開啟多邊形編輯器：\n{str(e)}")

    def _on_polygon_editor_completed(self, corners):
        """多邊形編輯器完成編輯"""
        self._sync_corners_from_editor(corners)
        QMessageBox.information(
            self, "角點已同步",
            f"已從編輯器同步 {len(corners)} 個角點到主視窗"
        )

    def _on_polygon_editor_corners_changed(self, corners):
        """多邊形編輯器角點變更（即時同步）"""
        self._sync_corners_from_editor(corners)

    def _sync_corners_from_editor(self, corners):
        """從編輯器同步角點"""
        # 清除現有角點
        self.corners.clear()
        self.map_widget.corners.clear()
        self.map_widget.markers.clear()

        # 添加新角點
        for lat, lon in corners:
            self.corners.append((lat, lon))

        # 重新初始化地圖並添加角點
        self.map_widget.init_map()
        for lat, lon in self.corners:
            self.map_widget.add_corner(lat, lon)

        # 更新 UI
        self.parameter_panel.update_corner_count(len(self.corners))
        self.update_statusbar()
        logger.info(f"已同步 {len(corners)} 個角點")

    def on_obstacles_changed(self, obstacles):
        """處理障礙物變更"""
        self.obstacles = obstacles
        logger.info(f"障礙物已更新: {len(obstacles)} 個")
    
    def on_show_help(self):
        """顯示說明"""
        help_text = """
        <h2>無人機路徑規劃工具</h2>
        <h3>基本操作：</h3>
        <ul>
            <li><b>新增邊界點：</b> 在地圖上點擊</li>
            <li><b>移動邊界點：</b> 拖動地圖上的標記</li>
            <li><b>預覽路徑：</b> 點擊"預覽"按鈕</li>
            <li><b>匯出航點：</b> 點擊"匯出"按鈕</li>
        </ul>
        <h3>快捷鍵：</h3>
        <ul>
            <li>Ctrl+N: 新建任務</li>
            <li>Ctrl+O: 開啟任務</li>
            <li>Ctrl+S: 儲存任務</li>
            <li>Ctrl+E: 匯出航點</li>
            <li>Ctrl+R: 清除全部</li>
        </ul>
        """
        
        QMessageBox.information(self, "使用說明", help_text)
    
    def on_about(self):
        """關於"""
        about_text = """
        <h2>無人機網格航線規劃工具 V2.0</h2>
        <p><b>基於 PyQt6 的專業級路徑規劃系統</b></p>
        <p>支援功能：</p>
        <ul>
            <li>Survey Grid 測繪任務</li>
            <li>多機群飛協調</li>
            <li>智能避撞系統</li>
            <li>MAVLink 航點匯出</li>
        </ul>
        <p>© 2026 UAV Path Planner Team</p>
        """
        
        QMessageBox.about(self, "關於", about_text)
    
    # ==========================================
    # 輔助函數
    # ==========================================
    
    def has_unsaved_changes(self):
        """檢查是否有未儲存的變更"""
        # TODO: 實現變更檢測
        return False
    
    def update_statusbar(self):
        """更新狀態列"""
        # 更新航點數量
        self.waypoint_label.setText(f"航點: {len(self.waypoints)}")
        
        # 更新邊界點數量
        if self.corners:
            self.statusBar().showMessage(f"邊界點: {len(self.corners)} 個", 2000)
    
    def closeEvent(self, event):
        """視窗關閉事件"""
        if self.current_mission and self.has_unsaved_changes():
            reply = QMessageBox.question(
                self, "未儲存的變更",
                "當前任務有未儲存的變更，確定要退出嗎？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        
        logger.info("應用程式關閉")
        event.accept()