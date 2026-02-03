"""
地圖組件模組
使用 folium + PyQt6 WebEngine 實現互動式地圖
"""

import os
import tempfile
from typing import List, Tuple, Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import pyqtSignal, pyqtSlot, QObject, QUrl

import folium
from folium import plugins

from config import Config
from logger_utils import logger


class MapBridge(QObject):
    """
    地圖橋接器
    用於 JavaScript 和 Python 之間的通訊
    """
    
    # 信號定義
    map_clicked = pyqtSignal(float, float)  # 地圖點擊信號 (lat, lon)
    marker_moved = pyqtSignal(int, float, float)  # 標記移動信號 (index, lat, lon)
    
    def __init__(self):
        super().__init__()
    
    @pyqtSlot(float, float)
    def on_map_click(self, lat, lon):
        """處理地圖點擊事件"""
        self.map_clicked.emit(lat, lon)
    
    @pyqtSlot(int, float, float)
    def on_marker_move(self, index, lat, lon):
        """處理標記移動事件"""
        self.marker_moved.emit(index, lat, lon)


class MapWidget(QWidget):
    """
    地圖組件
    
    提供互動式地圖顯示和編輯功能
    """
    
    # 信號定義
    corner_added = pyqtSignal(float, float)  # 新增邊界點
    corner_moved = pyqtSignal(int, float, float)  # 移動邊界點
    
    def __init__(self, parent=None):
        """初始化地圖組件"""
        super().__init__(parent)
        
        # 初始化變數
        self.corners = []
        self.markers = []
        self.paths = []
        self.current_map = None
        self.temp_html_file = None
        
        # 地圖模式
        self.edit_mode = True  # 編輯模式（可新增邊界點）
        
        # 建立 UI
        self.init_ui()
        
        # 初始化地圖
        self.init_map()
        
        logger.info("地圖組件初始化完成")
    
    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 創建 WebEngine 視圖
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)
        
        # 設置 Web Channel（用於 JavaScript 通訊）
        self.bridge = MapBridge()
        self.channel = QWebChannel()
        self.channel.registerObject('bridge', self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        
        # 連接信號
        self.bridge.map_clicked.connect(self.on_map_clicked)
        self.bridge.marker_moved.connect(self.on_marker_moved)
    
    def init_map(self):
        """初始化地圖"""
        try:
            # 創建 folium 地圖
            self.current_map = folium.Map(
                location=Config.DEFAULT_POSITION,
                zoom_start=Config.DEFAULT_ZOOM,
                tiles='OpenStreetMap',
                control_scale=True
            )
            
            # 添加圖層控制
            folium.LayerControl().add_to(self.current_map)
            
            # 添加全螢幕按鈕
            plugins.Fullscreen().add_to(self.current_map)
            
            # 添加滑鼠座標顯示
            plugins.MousePosition().add_to(self.current_map)
            
            # 添加測量工具
            plugins.MeasureControl().add_to(self.current_map)
            
            # 渲染地圖
            self.render_map()
            
            logger.info("地圖初始化成功")
            
        except Exception as e:
            logger.error(f"地圖初始化失敗: {e}")
            QMessageBox.critical(self, "地圖錯誤", f"地圖初始化失敗：\n{str(e)}")
    
    def render_map(self):
        """渲染地圖到 WebView"""
        try:
            # 生成 HTML
            html = self.current_map._repr_html_()
            
            # 添加 JavaScript 通訊代碼
            html = self.inject_javascript(html)
            
            # 儲存到臨時檔案
            if self.temp_html_file:
                try:
                    os.unlink(self.temp_html_file)
                except:
                    pass
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html)
                self.temp_html_file = f.name
            
            # 載入到 WebView
            self.web_view.setUrl(QUrl.fromLocalFile(self.temp_html_file))
            
        except Exception as e:
            logger.error(f"渲染地圖失敗: {e}")
    
    def inject_javascript(self, html: str) -> str:
        """
        注入 JavaScript 代碼以實現互動功能
        
        參數:
            html: 原始 HTML
        
        返回:
            注入 JavaScript 後的 HTML
        """
        js_code = """
        <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
        <script>
        // 初始化 Web Channel
        var bridge = null;
        
        new QWebChannel(qt.webChannelTransport, function(channel) {
            bridge = channel.objects.bridge;
            
            // 監聽地圖點擊事件
            if (typeof map !== 'undefined') {
                map.on('click', function(e) {
                    if (bridge) {
                        bridge.on_map_click(e.latlng.lat, e.latlng.lng);
                    }
                });
            }
        });
        
        // 標記移動處理函數
        function onMarkerDragEnd(index) {
            return function(e) {
                if (bridge) {
                    bridge.on_marker_move(index, e.target.getLatLng().lat, e.target.getLatLng().lng);
                }
            };
        }
        </script>
        """
        
        # 在 </body> 前插入
        html = html.replace('</body>', js_code + '</body>')
        
        return html
    
    def add_corner(self, lat: float, lon: float):
        """
        新增邊界點
        
        參數:
            lat: 緯度
            lon: 經度
        """
        index = len(self.corners)
        self.corners.append((lat, lon))
        
        # 在地圖上添加可拖動的標記
        marker = folium.Marker(
            location=[lat, lon],
            popup=f'邊界點 {index + 1}',
            icon=folium.Icon(color='green', icon='info-sign'),
            draggable=True
        )
        marker.add_to(self.current_map)
        self.markers.append(marker)
        
        # 如果有多個點，繪製多邊形
        if len(self.corners) >= 3:
            self.draw_boundary()
        
        # 重新渲染
        self.render_map()
        
        logger.info(f"新增邊界點 #{index + 1}: ({lat:.6f}, {lon:.6f})")
    
    def move_corner(self, index: int, lat: float, lon: float):
        """
        移動邊界點
        
        參數:
            index: 點的索引
            lat: 新緯度
            lon: 新經度
        """
        if 0 <= index < len(self.corners):
            self.corners[index] = (lat, lon)
            
            # 重新繪製邊界
            if len(self.corners) >= 3:
                self.draw_boundary()
            
            # 重新渲染
            self.render_map()
            
            logger.info(f"移動邊界點 #{index + 1}: ({lat:.6f}, {lon:.6f})")
    
    def draw_boundary(self):
        """繪製邊界多邊形"""
        if len(self.corners) < 3:
            return
        
        # 清除舊的多邊形
        # （在重新渲染時會自動清除）
        
        # 繪製新的多邊形
        folium.Polygon(
            locations=self.corners,
            color='#6aa84f',
            weight=2,
            fill=True,
            fill_color='#6aa84f',
            fill_opacity=0.1,
            popup='測繪區域'
        ).add_to(self.current_map)
    
    def display_survey(self, survey_mission):
        """
        顯示 Survey 任務
        
        參數:
            survey_mission: SurveyMission 物件
        """
        try:
            # 清除舊的路徑
            self.clear_paths()
            
            # 獲取航點序列
            waypoint_seq = survey_mission.waypoint_sequence
            
            if not waypoint_seq or len(waypoint_seq.waypoints) < 2:
                logger.warning("航點數量不足，無法顯示")
                return
            
            # 繪製飛行路徑
            path_coords = []
            for wp in waypoint_seq.waypoints:
                if wp.command in [16, 22]:  # NAV_WAYPOINT or TAKEOFF
                    path_coords.append([wp.lat, wp.lon])
            
            if len(path_coords) >= 2:
                folium.PolyLine(
                    locations=path_coords,
                    color='#08EC91',
                    weight=3,
                    opacity=0.8,
                    popup='飛行路徑'
                ).add_to(self.current_map)
                
                # 標記起點和終點
                if path_coords:
                    # 起點（綠色）
                    folium.Marker(
                        location=path_coords[0],
                        popup='起點',
                        icon=folium.Icon(color='green', icon='play')
                    ).add_to(self.current_map)
                    
                    # 終點（紅色）
                    folium.Marker(
                        location=path_coords[-1],
                        popup='終點',
                        icon=folium.Icon(color='red', icon='stop')
                    ).add_to(self.current_map)
            
            # 重新渲染
            self.render_map()
            
            # 調整視圖以包含所有點
            if path_coords:
                self.fit_bounds(path_coords)
            
            logger.info(f"顯示 Survey 任務：{len(path_coords)} 個航點")
            
        except Exception as e:
            logger.error(f"顯示 Survey 失敗: {e}")
    
    def fit_bounds(self, coordinates: List[List[float]]):
        """
        調整視圖以包含所有座標點
        
        參數:
            coordinates: 座標列表 [[lat, lon], ...]
        """
        if not coordinates:
            return
        
        try:
            # 計算邊界
            lats = [coord[0] for coord in coordinates]
            lons = [coord[1] for coord in coordinates]
            
            bounds = [
                [min(lats), min(lons)],
                [max(lats), max(lons)]
            ]
            
            # 設置地圖邊界
            self.current_map.fit_bounds(bounds, padding=[50, 50])
            
            # 重新渲染
            self.render_map()
            
        except Exception as e:
            logger.error(f"調整視圖失敗: {e}")
    
    def clear_corners(self):
        """清除邊界點"""
        self.corners.clear()
        self.markers.clear()
        
        # 重新初始化地圖
        self.init_map()
        
        logger.info("已清除邊界點")
    
    def clear_paths(self):
        """清除路徑"""
        self.paths.clear()
        
        # 重新初始化地圖（保留邊界點）
        self.init_map()
        
        # 重新添加邊界點
        if self.corners:
            for i, (lat, lon) in enumerate(self.corners):
                marker = folium.Marker(
                    location=[lat, lon],
                    popup=f'邊界點 {i + 1}',
                    icon=folium.Icon(color='green', icon='info-sign'),
                    draggable=True
                )
                marker.add_to(self.current_map)
                self.markers.append(marker)
            
            if len(self.corners) >= 3:
                self.draw_boundary()
            
            self.render_map()
        
        logger.info("已清除路徑")
    
    def reset_view(self):
        """重置視圖到預設位置"""
        self.current_map.location = Config.DEFAULT_POSITION
        self.current_map.zoom_start = Config.DEFAULT_ZOOM
        self.render_map()
        
        logger.info("視圖已重置")
    
    def change_tile_layer(self, tile_name: str):
        """
        切換地圖圖層
        
        參數:
            tile_name: 圖層名稱 ('OpenStreetMap', 'Satellite', etc.)
        """
        # 重新創建地圖（使用新圖層）
        self.current_map = folium.Map(
            location=self.current_map.location,
            zoom_start=self.current_map.zoom_start,
            tiles=tile_name,
            control_scale=True
        )
        
        # 重新添加標記和路徑
        # TODO: 實現標記和路徑的保留
        
        self.render_map()
        
        logger.info(f"切換地圖圖層：{tile_name}")
    
    def on_map_clicked(self, lat: float, lon: float):
        """處理地圖點擊事件"""
        if self.edit_mode:
            self.add_corner(lat, lon)
            self.corner_added.emit(lat, lon)
    
    def on_marker_moved(self, index: int, lat: float, lon: float):
        """處理標記移動事件"""
        self.move_corner(index, lat, lon)
        self.corner_moved.emit(index, lat, lon)
    
    def set_edit_mode(self, enabled: bool):
        """
        設置編輯模式
        
        參數:
            enabled: 是否啟用編輯模式
        """
        self.edit_mode = enabled
        logger.info(f"編輯模式：{'啟用' if enabled else '停用'}")
    
    def closeEvent(self, event):
        """關閉事件"""
        # 清理臨時檔案
        if self.temp_html_file:
            try:
                os.unlink(self.temp_html_file)
            except:
                pass
        
        event.accept()
