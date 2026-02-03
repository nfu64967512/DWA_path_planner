"""
主視窗模組
整合地圖、參數面板、任務面板等核心 UI 組件
"""

import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QToolBar, QMessageBox,
    QFileDialog, QLabel
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon

from config import Config
from logger_utils import logger
from mission import MissionManager


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
        
        # 視窗基本設置
        self.setWindowTitle(Config.WINDOW_TITLE)
        self.setGeometry(100, 100, Config.WINDOW_SIZE[0], Config.WINDOW_SIZE[1])
        self.setMinimumSize(*Config.MIN_WINDOW_SIZE)
        
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
        
        # 飛行參數
        self.flight_params = {
            'altitude': 50.0,
            'speed': 10.0,
            'angle': 0.0,
            'spacing': 20.0,
            'yaw_speed': 60.0,
            'subdivisions': 1,
            'region_spacing': 3.0,
        }
    
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
        
        # 設置分割比例（70% 地圖，30% 控制面板）
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(splitter)
        
        # 創建工具列
        self.create_toolbar()
        
        # 創建狀態列
        self.create_statusbar()
        
        # 創建選單
        self.create_menus()
    
    def create_map_widget(self):
        """創建地圖組件"""
        from ui.widgets.map_widget import MapWidget
        
        map_widget = MapWidget(self)
        
        # 連接信號
        map_widget.corner_added.connect(self.on_corner_added)
        map_widget.corner_moved.connect(self.on_corner_moved)
        
        return map_widget
    
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
        """創建選單"""
        menubar = self.menuBar()
        
        # 檔案選單
        file_menu = menubar.addMenu("&檔案")
        
        file_menu.addAction("新建任務", self.on_new_mission, "Ctrl+N")
        file_menu.addAction("開啟任務", self.on_open_mission, "Ctrl+O")
        file_menu.addAction("儲存任務", self.on_save_mission, "Ctrl+S")
        file_menu.addSeparator()
        file_menu.addAction("匯出航點", self.on_export_waypoints, "Ctrl+E")
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close, "Ctrl+Q")
        
        # 編輯選單
        edit_menu = menubar.addMenu("&編輯")
        
        edit_menu.addAction("清除路徑", self.on_clear_paths)
        edit_menu.addAction("清除邊界", self.on_clear_corners)
        edit_menu.addAction("清除全部", self.on_clear_all, "Ctrl+R")
        
        # 視圖選單
        view_menu = menubar.addMenu("&視圖")
        
        view_menu.addAction("重置視圖", self.on_reset_view)
        view_menu.addAction("顯示網格", self.on_toggle_grid)
        
        # 工具選單
        tools_menu = menubar.addMenu("&工具")
        
        tools_menu.addAction("相機配置", self.on_camera_config)
        tools_menu.addAction("飛行器配置", self.on_vehicle_config)
        tools_menu.addSeparator()
        tools_menu.addAction("障礙物管理", self.on_obstacle_manager)
        
        # 說明選單
        help_menu = menubar.addMenu("&說明")
        
        help_menu.addAction("使用說明", self.on_show_help)
        help_menu.addAction("關於", self.on_about)
    
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
        """處理新增邊界點"""
        self.corners.append((lat, lon))
        logger.info(f"新增邊界點 #{len(self.corners)}: ({lat:.6f}, {lon:.6f})")
        self.update_statusbar()
    
    def on_corner_moved(self, index, lat, lon):
        """處理移動邊界點"""
        if 0 <= index < len(self.corners):
            self.corners[index] = (lat, lon)
            logger.info(f"移動邊界點 #{index+1}: ({lat:.6f}, {lon:.6f})")
            self.update_statusbar()
    
    def on_parameters_changed(self, params):
        """處理參數變更"""
        self.flight_params.update(params)
        logger.info(f"參數已更新: {params}")
    
    def on_preview_paths(self):
        """預覽飛行路徑"""
        if len(self.corners) < Config.MIN_CORNERS:
            QMessageBox.warning(
                self, "邊界不足",
                f"需要至少 {Config.MIN_CORNERS} 個邊界點才能生成路徑"
            )
            return
        
        try:
            from mission import SurveyMissionBuilder
            
            # 創建 Survey 任務
            survey = (SurveyMissionBuilder()
                .set_name("預覽任務")
                .set_area(self.corners)
                .set_altitude(self.flight_params['altitude'])
                .set_speed(self.flight_params['speed'])
                .set_grid(
                    angle=self.flight_params['angle'],
                    spacing=self.flight_params['spacing'],
                    reduce_overlap=True
                )
                .set_subdivisions(self.flight_params['subdivisions'])
                .build())
            
            # 顯示在地圖上
            self.map_widget.display_survey(survey)
            
            # 更新狀態
            stats = survey.get_survey_statistics()
            self.waypoint_label.setText(f"航點: {stats.get('waypoint_count', 0)}")
            self.distance_label.setText(f"距離: {stats.get('total_distance', 0):.1f}m")
            
            self.statusBar().showMessage("路徑預覽完成", 3000)
            logger.info(f"預覽成功：{stats.get('waypoint_count', 0)} 個航點")
            
        except Exception as e:
            logger.error(f"預覽失敗: {e}")
            QMessageBox.critical(self, "預覽錯誤", f"生成路徑時發生錯誤：\n{str(e)}")
    
    def on_export_waypoints(self):
        """匯出航點"""
        if not self.current_mission:
            QMessageBox.warning(self, "無任務", "請先預覽路徑再匯出")
            return
        
        # 開啟匯出對話框
        filepath, _ = QFileDialog.getSaveFileName(
            self, "儲存航點檔案",
            "",
            "Waypoint Files (*.waypoints);;All Files (*)"
        )
        
        if filepath:
            try:
                success = self.mission_manager.export_waypoints(
                    self.current_mission,
                    filepath,
                    format='qgc'
                )
                
                if success:
                    QMessageBox.information(self, "匯出成功", f"航點已儲存至：\n{filepath}")
                    logger.info(f"匯出成功: {filepath}")
                else:
                    QMessageBox.warning(self, "匯出失敗", "無法儲存航點檔案")
                    
            except Exception as e:
                logger.error(f"匯出失敗: {e}")
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
        self.on_clear_all()
        
        # 創建新任務
        self.current_mission = self.mission_manager.create_mission("新任務")
        
        self.statusBar().showMessage("已創建新任務", 3000)
        logger.info("創建新任務")
    
    def on_open_mission(self):
        """開啟任務"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "開啟任務檔案",
            str(self.mission_manager.missions_dir),
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
        logger.info("已清除邊界")
    
    def on_clear_all(self):
        """清除全部"""
        reply = QMessageBox.question(
            self, "確認清除",
            "確定要清除所有標記和路徑嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
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
        pass
    
    def on_camera_config(self):
        """相機配置"""
        from ui.dialogs.camera_config import CameraConfigDialog
        
        dialog = CameraConfigDialog(self)
        dialog.exec()
    
    def on_vehicle_config(self):
        """飛行器配置"""
        from ui.dialogs.vehicle_config import VehicleConfigDialog
        
        dialog = VehicleConfigDialog(self)
        dialog.exec()
    
    def on_obstacle_manager(self):
        """障礙物管理"""
        # TODO: 實現障礙物管理對話框
        QMessageBox.information(self, "障礙物管理", "障礙物管理功能開發中")
    
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
