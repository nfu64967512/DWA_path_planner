"""
多邊形編輯器組件
獨立的地圖點擊編輯器，支援最多 100 個角點
用於定義 UAV 路徑規劃的飛行區域
"""

import os
import sys
import tempfile
import json
from typing import List, Tuple, Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMessageBox, QFileDialog, QSpinBox, QGroupBox, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QApplication,
    QMainWindow, QStatusBar, QToolBar, QComboBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtCore import pyqtSignal, Qt, QUrl, QTimer
from PyQt6.QtGui import QAction, QKeySequence

import folium
from folium import plugins

# 嘗試導入專案模組
try:
    from config import get_settings
    from utils.logger import get_logger
    settings = get_settings()
    logger = get_logger()
    DEFAULT_LAT = settings.map.default_lat
    DEFAULT_LON = settings.map.default_lon
    DEFAULT_ZOOM = settings.map.default_zoom
except ImportError:
    settings = None
    logger = None
    DEFAULT_LAT = 25.0330
    DEFAULT_LON = 121.5654
    DEFAULT_ZOOM = 15


# 常數定義
MAX_CORNERS = 100  # 最大角點數量
MIN_CORNERS_FOR_POLYGON = 3  # 最少角點數量（形成多邊形）


class ClickCapturePage(QWebEnginePage):
    """自定義 WebEngine 頁面，攔截點擊事件"""

    def __init__(self, parent, on_click_callback: Callable[[float, float], None]):
        super().__init__(parent)
        self.on_click_callback = on_click_callback

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        """處理 JavaScript 控制台訊息"""
        level_map = {0: 'INFO', 1: 'WARNING', 2: 'ERROR'}
        level_str = level_map.get(level, 'LOG')
        print(f"[JS {level_str}] {message}")

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        """攔截導航請求以接收點擊座標"""
        url_str = url.toString()

        # 攔截自定義 URL scheme
        if url_str.startswith('pyqt://click/'):
            try:
                parts = url_str.replace('pyqt://click/', '').split('/')
                lat = float(parts[0])
                lon = float(parts[1])
                print(f"[Python] 收到點擊: {lat}, {lon}")
                if self.on_click_callback:
                    self.on_click_callback(lat, lon)
            except Exception as e:
                print(f"[Python] 解析點擊座標失敗: {e}")
            return False  # 不實際導航

        return True  # 允許其他導航


class PolygonEditorWidget(QWidget):
    """
    多邊形編輯器組件

    提供地圖點擊編輯功能，支援最多 100 個角點
    """

    # 信號定義
    corner_added = pyqtSignal(float, float)      # 新增角點信號 (lat, lon)
    corner_removed = pyqtSignal(int)             # 移除角點信號 (index)
    corners_changed = pyqtSignal(list)           # 角點列表變更信號
    polygon_completed = pyqtSignal(list)         # 多邊形完成信號

    def __init__(self, parent=None, max_corners: int = MAX_CORNERS):
        """
        初始化多邊形編輯器

        參數:
            parent: 父組件
            max_corners: 最大角點數量（預設 100）
        """
        super().__init__(parent)

        # 初始化變數
        self.corners: List[Tuple[float, float]] = []
        self.max_corners = max_corners
        self.temp_html_file = None
        self.current_map = None
        self.edit_mode = True  # 編輯模式

        # 建立 UI
        self._init_ui()

        # 初始化地圖
        self._init_map()

        if logger:
            logger.info(f"多邊形編輯器初始化完成，最大角點數: {self.max_corners}")

    def _init_ui(self):
        """初始化 UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 創建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左側：地圖
        map_container = QWidget()
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)

        # 創建 WebEngine 視圖
        self.web_view = QWebEngineView()
        self.custom_page = ClickCapturePage(self.web_view, self._on_map_clicked)
        self.web_view.setPage(self.custom_page)

        # 設置 WebEngine 選項
        web_settings = self.custom_page.settings()
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)

        # 頁面載入完成後設置點擊處理
        self.web_view.loadFinished.connect(self._on_page_loaded)

        map_layout.addWidget(self.web_view)
        splitter.addWidget(map_container)

        # 右側：控制面板
        control_panel = self._create_control_panel()
        splitter.addWidget(control_panel)

        # 設置分割比例（75% 地圖，25% 控制面板）
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

    def _create_control_panel(self) -> QWidget:
        """創建控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # === 狀態顯示 ===
        status_group = QGroupBox("狀態")
        status_layout = QVBoxLayout(status_group)

        self.corner_count_label = QLabel(f"角點數量: 0 / {self.max_corners}")
        self.corner_count_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        status_layout.addWidget(self.corner_count_label)

        self.area_label = QLabel("面積: -- m²")
        status_layout.addWidget(self.area_label)

        self.status_label = QLabel("點擊地圖添加角點")
        self.status_label.setStyleSheet("color: #4CAF50;")
        status_layout.addWidget(self.status_label)

        layout.addWidget(status_group)

        # === 角點列表 ===
        list_group = QGroupBox("角點列表")
        list_layout = QVBoxLayout(list_group)

        self.corner_table = QTableWidget()
        self.corner_table.setColumnCount(3)
        self.corner_table.setHorizontalHeaderLabels(["#", "緯度", "經度"])
        self.corner_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.corner_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.corner_table.setMaximumHeight(200)
        list_layout.addWidget(self.corner_table)

        # 刪除選中按鈕
        delete_btn = QPushButton("🗑 刪除選中角點")
        delete_btn.clicked.connect(self._on_delete_selected)
        list_layout.addWidget(delete_btn)

        layout.addWidget(list_group)

        # === 操作按鈕 ===
        action_group = QGroupBox("操作")
        action_layout = QVBoxLayout(action_group)

        # 清除全部
        clear_btn = QPushButton("🧹 清除全部角點")
        clear_btn.clicked.connect(self.clear_all_corners)
        action_layout.addWidget(clear_btn)

        # 撤銷上一個
        undo_btn = QPushButton("↩ 撤銷上一個角點")
        undo_btn.clicked.connect(self.undo_last_corner)
        action_layout.addWidget(undo_btn)

        # 閉合多邊形
        close_btn = QPushButton("⬡ 閉合多邊形")
        close_btn.clicked.connect(self._on_close_polygon)
        action_layout.addWidget(close_btn)

        layout.addWidget(action_group)

        # === 匯入/匯出 ===
        io_group = QGroupBox("匯入/匯出")
        io_layout = QVBoxLayout(io_group)

        export_btn = QPushButton("📤 匯出角點 (JSON)")
        export_btn.clicked.connect(self._on_export_corners)
        io_layout.addWidget(export_btn)

        import_btn = QPushButton("📥 匯入角點 (JSON)")
        import_btn.clicked.connect(self._on_import_corners)
        io_layout.addWidget(import_btn)

        layout.addWidget(io_group)

        # 添加彈性空間
        layout.addStretch()

        # === 說明 ===
        help_label = QLabel(
            "💡 提示:\n"
            "• 左鍵點擊地圖添加角點\n"
            f"• 最多可添加 {self.max_corners} 個角點\n"
            "• 至少需要 3 個角點形成多邊形\n"
            "• 可使用滾輪縮放地圖"
        )
        help_label.setStyleSheet("color: #666; font-size: 11px;")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        return panel

    def _init_map(self):
        """初始化地圖"""
        try:
            # 創建 folium 地圖
            self.current_map = folium.Map(
                location=(DEFAULT_LAT, DEFAULT_LON),
                zoom_start=DEFAULT_ZOOM,
                tiles=None,
                control_scale=True
            )

            # 添加 Google 衛星圖層（預設）
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                attr='Google Satellite',
                name='Google 衛星',
                overlay=False,
                control=True
            ).add_to(self.current_map)

            # 添加 Google 地圖圖層
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
                attr='Google Maps',
                name='Google 地圖',
                overlay=False,
                control=True
            ).add_to(self.current_map)

            # 添加 OpenStreetMap 圖層
            folium.TileLayer(
                tiles='OpenStreetMap',
                name='OpenStreetMap',
                overlay=False,
                control=True
            ).add_to(self.current_map)

            # 添加圖層控制
            folium.LayerControl().add_to(self.current_map)

            # 添加全螢幕按鈕
            plugins.Fullscreen().add_to(self.current_map)

            # 添加滑鼠座標顯示
            plugins.MousePosition(
                position='topright',
                separator=' | ',
                prefix='座標: '
            ).add_to(self.current_map)

            # 添加測量工具
            plugins.MeasureControl(
                position='topleft',
                primary_length_unit='meters',
                secondary_length_unit='kilometers',
                primary_area_unit='sqmeters'
            ).add_to(self.current_map)

            # 渲染地圖
            self._render_map()

            if logger:
                logger.info("多邊形編輯器地圖初始化成功")

        except Exception as e:
            if logger:
                logger.error(f"地圖初始化失敗: {e}")
            QMessageBox.critical(self, "地圖錯誤", f"地圖初始化失敗：\n{str(e)}")

    def _render_map(self):
        """渲染地圖到 WebView"""
        try:
            # 重新創建地圖以包含所有角點
            self.current_map = folium.Map(
                location=(DEFAULT_LAT, DEFAULT_LON),
                zoom_start=DEFAULT_ZOOM,
                tiles=None,
                control_scale=True
            )

            # 添加圖層
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                attr='Google Satellite',
                name='Google 衛星',
                overlay=False,
                control=True
            ).add_to(self.current_map)

            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
                attr='Google Maps',
                name='Google 地圖',
                overlay=False,
                control=True
            ).add_to(self.current_map)

            folium.TileLayer(
                tiles='OpenStreetMap',
                name='OpenStreetMap',
                overlay=False,
                control=True
            ).add_to(self.current_map)

            folium.LayerControl().add_to(self.current_map)
            plugins.Fullscreen().add_to(self.current_map)
            plugins.MousePosition(position='topright', separator=' | ', prefix='座標: ').add_to(self.current_map)
            plugins.MeasureControl(position='topleft').add_to(self.current_map)

            # 添加角點標記
            for i, (lat, lon) in enumerate(self.corners):
                folium.Marker(
                    location=[lat, lon],
                    popup=f'角點 {i + 1}<br>({lat:.6f}, {lon:.6f})',
                    icon=folium.DivIcon(
                        html=f'''
                        <div style="
                            background-color: #4CAF50;
                            color: white;
                            border-radius: 50%;
                            width: 24px;
                            height: 24px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            font-weight: bold;
                            font-size: 12px;
                            border: 2px solid white;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                        ">{i + 1}</div>
                        ''',
                        icon_size=(24, 24),
                        icon_anchor=(12, 12)
                    )
                ).add_to(self.current_map)

            # 如果有足夠的角點，繪製多邊形
            if len(self.corners) >= MIN_CORNERS_FOR_POLYGON:
                folium.Polygon(
                    locations=self.corners,
                    color='#4CAF50',
                    weight=3,
                    fill=True,
                    fill_color='#4CAF50',
                    fill_opacity=0.2,
                    popup='飛行區域'
                ).add_to(self.current_map)
            elif len(self.corners) >= 2:
                # 繪製連線
                folium.PolyLine(
                    locations=self.corners,
                    color='#4CAF50',
                    weight=2,
                    dash_array='5, 5'
                ).add_to(self.current_map)

            # 調整視圖以包含所有角點
            if self.corners:
                self.current_map.fit_bounds(
                    [[min(c[0] for c in self.corners), min(c[1] for c in self.corners)],
                     [max(c[0] for c in self.corners), max(c[1] for c in self.corners)]],
                    padding=[50, 50]
                )

            # 生成 HTML
            html = self.current_map._repr_html_()
            html = self._inject_click_handler(html)

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
            if logger:
                logger.error(f"渲染地圖失敗: {e}")

    def _inject_click_handler(self, html: str) -> str:
        """注入點擊處理 JavaScript"""
        js_code = """
        <style>
        .leaflet-container {
            cursor: crosshair !important;
        }
        .leaflet-interactive {
            cursor: crosshair !important;
        }
        .click-feedback {
            position: absolute;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(76, 175, 80, 0.95);
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            font-size: 14px;
            z-index: 1000;
            pointer-events: none;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        </style>
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(function() {
                setupMapClickHandler();
            }, 1000);
        });

        function setupMapClickHandler() {
            var mapObj = null;

            // 查找地圖物件
            for (var key in window) {
                try {
                    var obj = window[key];
                    if (obj && obj._container &&
                        obj._container.classList &&
                        obj._container.classList.contains('leaflet-container') &&
                        typeof obj.on === 'function') {
                        mapObj = obj;
                        console.log('找到地圖物件: ' + key);
                        break;
                    }
                } catch(e) {}
            }

            if (!mapObj) {
                console.log('等待地圖初始化...');
                setTimeout(setupMapClickHandler, 500);
                return;
            }

            // 添加點擊提示
            var feedback = document.createElement('div');
            feedback.className = 'click-feedback';
            feedback.textContent = '🖱️ 點擊地圖添加角點';
            mapObj._container.appendChild(feedback);

            // 3秒後隱藏提示
            setTimeout(function() {
                feedback.style.opacity = '0';
                feedback.style.transition = 'opacity 0.5s';
                setTimeout(function() {
                    feedback.style.display = 'none';
                }, 500);
            }, 3000);

            // 綁定點擊事件
            mapObj.on('click', function(e) {
                var lat = e.latlng.lat;
                var lng = e.latlng.lng;
                console.log('地圖點擊: ' + lat + ', ' + lng);

                // 通過 URL scheme 通知 Python
                window.location.href = 'pyqt://click/' + lat + '/' + lng;

                // 視覺反饋
                var marker = L.circleMarker([lat, lng], {
                    radius: 12,
                    color: '#4CAF50',
                    fillColor: '#4CAF50',
                    fillOpacity: 0.8,
                    weight: 3
                }).addTo(mapObj);

                // 脈衝動畫
                var pulseRadius = 12;
                var pulseInterval = setInterval(function() {
                    pulseRadius += 2;
                    marker.setRadius(pulseRadius);
                    marker.setStyle({fillOpacity: 0.8 - (pulseRadius - 12) / 30});
                    if (pulseRadius > 30) {
                        clearInterval(pulseInterval);
                        mapObj.removeLayer(marker);
                    }
                }, 30);
            });

            console.log('✅ 地圖點擊事件已綁定');
        }
        </script>
        """

        return html.replace('</body>', js_code + '</body>')

    def _on_page_loaded(self, ok):
        """頁面載入完成處理"""
        if ok:
            # 延遲設置點擊處理器
            QTimer.singleShot(1500, self._setup_click_handler)

    def _setup_click_handler(self):
        """設置點擊處理器（備用方法）"""
        js_code = """
        (function() {
            var mapObj = null;
            for (var key in window) {
                try {
                    if (key.startsWith('map_') && window[key] && typeof window[key].on === 'function') {
                        mapObj = window[key];
                        break;
                    }
                } catch(e) {}
            }
            if (mapObj) {
                mapObj.off('click');
                mapObj.on('click', function(e) {
                    window.location.href = 'pyqt://click/' + e.latlng.lat + '/' + e.latlng.lng;
                });
                return 'OK';
            }
            return 'NO_MAP';
        })();
        """
        self.custom_page.runJavaScript(js_code)

    def _on_map_clicked(self, lat: float, lon: float):
        """處理地圖點擊事件"""
        if not self.edit_mode:
            return

        if len(self.corners) >= self.max_corners:
            QMessageBox.warning(
                self, "已達上限",
                f"已達到最大角點數量 ({self.max_corners} 個)！\n"
                "請先刪除一些角點再添加新的。"
            )
            return

        # 添加角點
        self.add_corner(lat, lon)

    def add_corner(self, lat: float, lon: float):
        """
        添加角點

        參數:
            lat: 緯度
            lon: 經度
        """
        if len(self.corners) >= self.max_corners:
            return

        self.corners.append((lat, lon))

        # 更新 UI
        self._update_ui()

        # 重新渲染地圖
        self._render_map()

        # 發送信號
        self.corner_added.emit(lat, lon)
        self.corners_changed.emit(self.corners.copy())

        if logger:
            logger.info(f"添加角點 #{len(self.corners)}: ({lat:.6f}, {lon:.6f})")

    def remove_corner(self, index: int):
        """
        移除角點

        參數:
            index: 角點索引
        """
        if 0 <= index < len(self.corners):
            removed = self.corners.pop(index)

            # 更新 UI
            self._update_ui()

            # 重新渲染地圖
            self._render_map()

            # 發送信號
            self.corner_removed.emit(index)
            self.corners_changed.emit(self.corners.copy())

            if logger:
                logger.info(f"移除角點 #{index + 1}: ({removed[0]:.6f}, {removed[1]:.6f})")

    def undo_last_corner(self):
        """撤銷上一個角點"""
        if self.corners:
            self.remove_corner(len(self.corners) - 1)

    def clear_all_corners(self):
        """清除所有角點"""
        if not self.corners:
            return

        reply = QMessageBox.question(
            self, "確認清除",
            f"確定要清除所有 {len(self.corners)} 個角點嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.corners.clear()
            self._update_ui()
            self._render_map()
            self.corners_changed.emit([])

            if logger:
                logger.info("已清除所有角點")

    def _update_ui(self):
        """更新 UI 顯示"""
        # 更新角點數量
        count = len(self.corners)
        self.corner_count_label.setText(f"角點數量: {count} / {self.max_corners}")

        # 更新狀態
        if count == 0:
            self.status_label.setText("點擊地圖添加角點")
            self.status_label.setStyleSheet("color: #4CAF50;")
        elif count < MIN_CORNERS_FOR_POLYGON:
            self.status_label.setText(f"還需要 {MIN_CORNERS_FOR_POLYGON - count} 個角點形成多邊形")
            self.status_label.setStyleSheet("color: #FF9800;")
        elif count >= self.max_corners:
            self.status_label.setText("已達最大角點數量！")
            self.status_label.setStyleSheet("color: #F44336;")
        else:
            self.status_label.setText("✓ 多邊形已形成")
            self.status_label.setStyleSheet("color: #4CAF50;")

        # 更新面積
        if count >= MIN_CORNERS_FOR_POLYGON:
            area = self._calculate_area()
            if area < 10000:
                self.area_label.setText(f"面積: {area:.1f} m²")
            else:
                self.area_label.setText(f"面積: {area/10000:.3f} 公頃")
        else:
            self.area_label.setText("面積: -- m²")

        # 更新角點列表
        self.corner_table.setRowCount(count)
        for i, (lat, lon) in enumerate(self.corners):
            self.corner_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.corner_table.setItem(i, 1, QTableWidgetItem(f"{lat:.6f}"))
            self.corner_table.setItem(i, 2, QTableWidgetItem(f"{lon:.6f}"))

    def _calculate_area(self) -> float:
        """計算多邊形面積（平方公尺）"""
        if len(self.corners) < MIN_CORNERS_FOR_POLYGON:
            return 0.0

        import math

        # 計算中心點
        center_lat = sum(c[0] for c in self.corners) / len(self.corners)
        center_lon = sum(c[1] for c in self.corners) / len(self.corners)

        # 轉換到平面座標（公尺）
        def latlon_to_xy(lat, lon):
            x = (lon - center_lon) * 111111.0 * math.cos(math.radians(center_lat))
            y = (lat - center_lat) * 111111.0
            return x, y

        polygon_xy = [latlon_to_xy(lat, lon) for lat, lon in self.corners]

        # Shoelace 公式計算面積
        area = 0.0
        n = len(polygon_xy)
        for i in range(n):
            j = (i + 1) % n
            area += polygon_xy[i][0] * polygon_xy[j][1]
            area -= polygon_xy[j][0] * polygon_xy[i][1]

        return abs(area) / 2.0

    def _on_delete_selected(self):
        """刪除選中的角點"""
        selected_rows = set(item.row() for item in self.corner_table.selectedItems())
        if not selected_rows:
            return

        # 從後往前刪除，避免索引問題
        for index in sorted(selected_rows, reverse=True):
            self.remove_corner(index)

    def _on_close_polygon(self):
        """閉合多邊形"""
        if len(self.corners) < MIN_CORNERS_FOR_POLYGON:
            QMessageBox.warning(
                self, "角點不足",
                f"至少需要 {MIN_CORNERS_FOR_POLYGON} 個角點才能形成多邊形！"
            )
            return

        # 發送多邊形完成信號
        self.polygon_completed.emit(self.corners.copy())

        QMessageBox.information(
            self, "多邊形已完成",
            f"多邊形已完成！\n\n"
            f"角點數量: {len(self.corners)}\n"
            f"面積: {self._calculate_area():.1f} m²"
        )

    def _on_export_corners(self):
        """匯出角點"""
        if not self.corners:
            QMessageBox.warning(self, "無資料", "沒有角點可匯出")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "匯出角點",
            "polygon_corners.json",
            "JSON 檔案 (*.json);;所有檔案 (*)"
        )

        if filepath:
            try:
                data = {
                    "corners": [{"lat": lat, "lon": lon} for lat, lon in self.corners],
                    "count": len(self.corners),
                    "area_sqm": self._calculate_area()
                }

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                QMessageBox.information(
                    self, "匯出成功",
                    f"已匯出 {len(self.corners)} 個角點到:\n{filepath}"
                )

                if logger:
                    logger.info(f"匯出角點: {filepath}")

            except Exception as e:
                QMessageBox.critical(self, "匯出失敗", f"匯出時發生錯誤：\n{str(e)}")

    def _on_import_corners(self):
        """匯入角點"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "匯入角點",
            "",
            "JSON 檔案 (*.json);;所有檔案 (*)"
        )

        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                corners = data.get("corners", [])
                if not corners:
                    QMessageBox.warning(self, "無資料", "檔案中沒有角點資料")
                    return

                # 檢查數量限制
                if len(corners) > self.max_corners:
                    reply = QMessageBox.question(
                        self, "角點數量超過上限",
                        f"檔案包含 {len(corners)} 個角點，超過上限 {self.max_corners}。\n"
                        f"是否只匯入前 {self.max_corners} 個？",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        return
                    corners = corners[:self.max_corners]

                # 清除現有角點並匯入
                self.corners.clear()
                for corner in corners:
                    self.corners.append((corner["lat"], corner["lon"]))

                self._update_ui()
                self._render_map()
                self.corners_changed.emit(self.corners.copy())

                QMessageBox.information(
                    self, "匯入成功",
                    f"已匯入 {len(self.corners)} 個角點"
                )

                if logger:
                    logger.info(f"匯入角點: {filepath}")

            except Exception as e:
                QMessageBox.critical(self, "匯入失敗", f"匯入時發生錯誤：\n{str(e)}")

    def get_corners(self) -> List[Tuple[float, float]]:
        """獲取所有角點"""
        return self.corners.copy()

    def set_corners(self, corners: List[Tuple[float, float]]):
        """設置角點列表"""
        self.corners = corners[:self.max_corners]
        self._update_ui()
        self._render_map()
        self.corners_changed.emit(self.corners.copy())

    def set_edit_mode(self, enabled: bool):
        """設置編輯模式"""
        self.edit_mode = enabled

    def closeEvent(self, event):
        """關閉事件"""
        if self.temp_html_file:
            try:
                os.unlink(self.temp_html_file)
            except:
                pass
        event.accept()


class PolygonEditorWindow(QMainWindow):
    """
    多邊形編輯器獨立視窗

    可作為獨立程式運行
    """

    # 信號定義
    polygon_completed = pyqtSignal(list)

    def __init__(self, max_corners: int = MAX_CORNERS):
        super().__init__()

        self.setWindowTitle("🗺️ UAV 飛行區域編輯器")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(800, 600)

        # 創建編輯器組件
        self.editor = PolygonEditorWidget(self, max_corners=max_corners)
        self.setCentralWidget(self.editor)

        # 連接信號
        self.editor.polygon_completed.connect(self._on_polygon_completed)

        # 創建工具列
        self._create_toolbar()

        # 創建狀態列
        self._create_statusbar()

        # 創建選單
        self._create_menus()

    def _create_toolbar(self):
        """創建工具列"""
        toolbar = QToolBar("主工具列")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # 清除
        clear_action = QAction("🧹 清除全部", self)
        clear_action.setShortcut(QKeySequence("Ctrl+D"))
        clear_action.triggered.connect(self.editor.clear_all_corners)
        toolbar.addAction(clear_action)

        # 撤銷
        undo_action = QAction("↩ 撤銷", self)
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        undo_action.triggered.connect(self.editor.undo_last_corner)
        toolbar.addAction(undo_action)

        toolbar.addSeparator()

        # 完成
        complete_action = QAction("✅ 完成編輯", self)
        complete_action.setShortcut(QKeySequence("Ctrl+Return"))
        complete_action.triggered.connect(self.editor._on_close_polygon)
        toolbar.addAction(complete_action)

        toolbar.addSeparator()

        # 匯出
        export_action = QAction("📤 匯出", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.editor._on_export_corners)
        toolbar.addAction(export_action)

        # 匯入
        import_action = QAction("📥 匯入", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self.editor._on_import_corners)
        toolbar.addAction(import_action)

    def _create_statusbar(self):
        """創建狀態列"""
        statusbar = QStatusBar()
        self.setStatusBar(statusbar)
        statusbar.showMessage("點擊地圖添加角點，最多可添加 100 個角點")

    def _create_menus(self):
        """創建選單"""
        menubar = self.menuBar()

        # 檔案選單
        file_menu = menubar.addMenu("檔案(&F)")

        export_action = file_menu.addAction("匯出角點")
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.editor._on_export_corners)

        import_action = file_menu.addAction("匯入角點")
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self.editor._on_import_corners)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("退出")
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)

        # 編輯選單
        edit_menu = menubar.addMenu("編輯(&E)")

        undo_action = edit_menu.addAction("撤銷上一個角點")
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        undo_action.triggered.connect(self.editor.undo_last_corner)

        clear_action = edit_menu.addAction("清除全部")
        clear_action.setShortcut(QKeySequence("Ctrl+D"))
        clear_action.triggered.connect(self.editor.clear_all_corners)

        # 說明選單
        help_menu = menubar.addMenu("說明(&H)")

        about_action = help_menu.addAction("關於")
        about_action.triggered.connect(self._show_about)

    def _show_about(self):
        """顯示關於對話框"""
        QMessageBox.about(
            self, "關於",
            "<h2>UAV 飛行區域編輯器</h2>"
            "<p>用於定義無人機飛行區域的多邊形編輯工具</p>"
            "<p><b>功能:</b></p>"
            "<ul>"
            "<li>點擊地圖添加角點（最多 100 個）</li>"
            "<li>支援 Google 衛星圖/地圖/OSM</li>"
            "<li>匯入/匯出 JSON 格式</li>"
            "<li>自動計算面積</li>"
            "</ul>"
            "<p>© 2026 UAV Path Planner Team</p>"
        )

    def _on_polygon_completed(self, corners: List[Tuple[float, float]]):
        """多邊形完成處理"""
        self.polygon_completed.emit(corners)

    def get_corners(self) -> List[Tuple[float, float]]:
        """獲取所有角點"""
        return self.editor.get_corners()


def main():
    """獨立運行入口"""
    # 設置 OpenGL 共享上下文
    from PyQt6.QtCore import Qt
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    app.setApplicationName("UAV 飛行區域編輯器")

    window = PolygonEditorWindow(max_corners=100)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
