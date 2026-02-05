"""
地圖組件模組
使用 folium + PyQt6 WebEngine 實現互動式地圖
"""

import os
import tempfile
from typing import List, Tuple, Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import pyqtSignal, pyqtSlot, QObject, QUrl, Qt

import folium
from folium import plugins

from config import get_settings
from utils.logger import get_logger

# 獲取配置和日誌實例
settings = get_settings()
logger = get_logger()

# 常數定義
MAX_CORNERS = 100  # 最大角點數量
MIN_CORNERS_FOR_POLYGON = 3  # 最少角點數量


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

        # 創建自定義頁面（攔截 URL 來接收點擊事件）
        from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

        class ClickCapturePage(QWebEnginePage):
            def __init__(self, parent, widget):
                super().__init__(parent)
                self.widget = widget

            def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
                level_map = {0: 'INFO', 1: 'WARNING', 2: 'ERROR'}
                level_str = level_map.get(level, 'LOG')
                print(f"[JS {level_str}] {message}")

            def acceptNavigationRequest(self, url, nav_type, is_main_frame):
                url_str = url.toString()
                # 攔截自定義 URL scheme
                if url_str.startswith('pyqt://click/'):
                    try:
                        parts = url_str.replace('pyqt://click/', '').split('/')
                        lat = float(parts[0])
                        lon = float(parts[1])
                        print(f"[Python] 收到點擊: {lat}, {lon}")
                        self.widget.on_map_clicked(lat, lon)
                    except Exception as e:
                        print(f"[Python] 解析點擊座標失敗: {e}")
                    return False  # 不實際導航
                return True  # 允許其他導航

        self.custom_page = ClickCapturePage(self.web_view, self)
        self.web_view.setPage(self.custom_page)

        # 允許載入外部資源（修復 Leaflet CDN 問題）
        web_settings = self.custom_page.settings()
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)

        # 啟用右鍵選單
        self.web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        # 頁面載入完成後設置點擊處理
        self.web_view.loadFinished.connect(self._on_page_loaded)

        layout.addWidget(self.web_view)
    
    def init_map(self):
        """初始化地圖"""
        try:
            # 創建 folium 地圖（使用 Google 衛星圖資）
            self.current_map = folium.Map(
                location=(settings.map.default_lat, settings.map.default_lon),
                zoom_start=settings.map.default_zoom,
                tiles=None,  # 不使用預設圖層
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
            plugins.MousePosition().add_to(self.current_map)
            
            # 添加測量工具
            plugins.MeasureControl().add_to(self.current_map)

            # 添加繪圖工具（用於添加邊界點）
            draw_options = {
                'polyline': False,
                'polygon': False,
                'rectangle': False,
                'circle': False,
                'circlemarker': False,
                'marker': True,  # 只啟用標記點
            }
            plugins.Draw(
                export=False,
                position='topleft',
                draw_options=draw_options,
            ).add_to(self.current_map)

            # 渲染地圖
            self.render_map()
            
            logger.info("地圖初始化成功")
            
        except Exception as e:
            logger.error(f"地圖初始化失敗: {e}")
            QMessageBox.critical(self, "地圖錯誤", f"地圖初始化失敗：\n{str(e)}")
    
    def _on_page_loaded(self, ok):
        """頁面載入完成後設置點擊處理"""
        if not ok:
            logger.warning("頁面載入失敗")
            return

        # 延遲執行以確保 Leaflet 完全初始化
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, self._setup_map_click_handler)

    def _setup_map_click_handler(self):
        """設置地圖點擊處理器"""
        js_code = """
        (function() {
            // 查找地圖物件 - 多種方式嘗試
            var mapObj = null;

            // 方式1: 查找 map_ 開頭的變數
            for (var key in window) {
                try {
                    if (key.startsWith('map_') && window[key] && typeof window[key].on === 'function') {
                        mapObj = window[key];
                        console.log('找到地圖物件(map_): ' + key);
                        break;
                    }
                } catch(e) {}
            }

            // 方式2: 查找 L.map 實例
            if (!mapObj) {
                var maps = document.querySelectorAll('.leaflet-container');
                if (maps.length > 0) {
                    for (var key in window) {
                        try {
                            if (window[key] && window[key]._container && window[key]._container.classList.contains('leaflet-container')) {
                                mapObj = window[key];
                                console.log('找到地圖物件(container): ' + key);
                                break;
                            }
                        } catch(e) {}
                    }
                }
            }

            if (!mapObj) {
                console.error('無法找到地圖物件，將在 500ms 後重試');
                setTimeout(function() {
                    for (var key in window) {
                        try {
                            if (key.startsWith('map_') && window[key] && typeof window[key].on === 'function') {
                                mapObj = window[key];
                                setupClickHandler(mapObj);
                                break;
                            }
                        } catch(e) {}
                    }
                }, 500);
                return 'RETRY';
            }

            function setupClickHandler(map) {
                // 移除舊的點擊事件（避免重複）
                map.off('click');

                // 綁定點擊事件
                map.on('click', function(e) {
                    console.log('地圖點擊: ' + e.latlng.lat + ', ' + e.latlng.lng);
                    window.location.href = 'pyqt://click/' + e.latlng.lat + '/' + e.latlng.lng;

                    // 視覺反饋 - 短暫顯示點擊位置
                    var clickMarker = L.circleMarker([e.latlng.lat, e.latlng.lng], {
                        radius: 8,
                        color: '#00ff00',
                        fillColor: '#00ff00',
                        fillOpacity: 0.5
                    }).addTo(map);

                    setTimeout(function() {
                        map.removeLayer(clickMarker);
                    }, 300);
                });

                // 綁定 Draw 插件事件
                map.on('draw:created', function(e) {
                    if (e.layer && e.layer.getLatLng) {
                        var latlng = e.layer.getLatLng();
                        console.log('Draw 標記: ' + latlng.lat + ', ' + latlng.lng);
                        window.location.href = 'pyqt://click/' + latlng.lat + '/' + latlng.lng;
                    }
                });

                console.log('✓ 地圖點擊事件已綁定');
            }

            setupClickHandler(mapObj);
            return 'OK';
        })();
        """

        def callback(result):
            if result == 'OK':
                logger.info("地圖點擊處理器設置成功")
            elif result == 'RETRY':
                logger.info("地圖點擊處理器將延遲重試")
            else:
                logger.warning(f"地圖點擊處理器設置結果: {result}")

        self.custom_page.runJavaScript(js_code, callback)

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
        import re

        # 從 HTML 中提取 folium 生成的地圖變數名稱
        map_var_match = re.search(r'var\s+(map_[a-f0-9]+)\s*=\s*L\.map', html)
        map_var_name = map_var_match.group(1) if map_var_match else None
        logger.info(f"找到 folium 地圖變數: {map_var_name}")

        # 使用普通字串避免 f-string 的大括號問題
        js_code = """
        <style>
        /* 強制使用十字游標 - 點擊添加模式 */
        .leaflet-container,
        .leaflet-container *,
        .leaflet-interactive,
        .leaflet-overlay-pane,
        .leaflet-overlay-pane *,
        .leaflet-map-pane,
        .leaflet-map-pane * {
            cursor: crosshair !important;
        }
        .leaflet-marker-draggable {
            cursor: move !important;
        }
        .leaflet-control,
        .leaflet-control * {
            cursor: pointer !important;
        }
        /* 點擊提示 */
        .click-hint {
            position: absolute;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(76, 175, 80, 0.95);
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            font-size: 14px;
            font-weight: bold;
            z-index: 1000;
            pointer-events: none;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        /* 角點計數器 */
        .corner-counter {
            position: absolute;
            bottom: 30px;
            left: 10px;
            background: rgba(0, 0, 0, 0.7);
            color: #4CAF50;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 1000;
            pointer-events: none;
        }
        </style>
        <script>
        // 全域變數
        var mapClickEnabled = true;
        var cornerCount = 0;
        var maxCorners = 100;
        var FOLIUM_MAP_VAR = '__MAP_VAR_PLACEHOLDER__';  // 由 Python 替換

        // 等待頁面載入完成後設置點擊處理
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(function() {
                setupMapClickHandler();
            }, 500);
        });

        // 備用：window.onload
        window.onload = function() {
            setTimeout(function() {
                if (!window.mapClickHandlerReady) {
                    setupMapClickHandler();
                }
            }, 1000);
        };

        function setupMapClickHandler() {
            var mapObj = null;

            // 方式1: 直接使用已知的 folium 地圖變數名
            if (FOLIUM_MAP_VAR && FOLIUM_MAP_VAR !== 'null' && window[FOLIUM_MAP_VAR]) {
                mapObj = window[FOLIUM_MAP_VAR];
                console.log('直接找到 folium 地圖: ' + FOLIUM_MAP_VAR);
            }

            // 方式2: 查找 map_ 開頭的變數
            if (!mapObj) {
                for (var key in window) {
                    try {
                        if (key.startsWith('map_') && window[key] && typeof window[key].on === 'function') {
                            mapObj = window[key];
                            console.log('找到地圖物件: ' + key);
                            break;
                        }
                    } catch(e) {}
                }
            }

            // 方式3: 查找 leaflet-container
            if (!mapObj) {
                for (var key in window) {
                    try {
                        var obj = window[key];
                        if (obj && obj._container &&
                            obj._container.classList &&
                            obj._container.classList.contains('leaflet-container') &&
                            typeof obj.on === 'function') {
                            mapObj = obj;
                            console.log('找到地圖物件(container): ' + key);
                            break;
                        }
                    } catch(e) {}
                }
            }

            if (!mapObj) {
                console.log('等待地圖初始化... 500ms後重試');
                setTimeout(setupMapClickHandler, 500);
                return;
            }

            window.mapClickHandlerReady = true;
            window.currentMap = mapObj;

            // 移除預設的拖動游標樣式
            mapObj._container.style.cursor = 'crosshair';

            // 添加點擊提示
            var hint = document.createElement('div');
            hint.className = 'click-hint';
            hint.innerHTML = '🖱️ 單擊地圖添加角點 (最多 ' + maxCorners + ' 個)';
            mapObj._container.appendChild(hint);

            // 添加角點計數器
            var counter = document.createElement('div');
            counter.className = 'corner-counter';
            counter.id = 'corner-counter';
            counter.innerHTML = '角點: 0 / ' + maxCorners;
            mapObj._container.appendChild(counter);

            // 3秒後隱藏提示
            setTimeout(function() {
                hint.style.opacity = '0';
                hint.style.transition = 'opacity 0.5s';
                setTimeout(function() { hint.style.display = 'none'; }, 500);
            }, 3000);

            // 移除舊的點擊事件
            mapObj.off('click');

            // 綁定點擊事件
            mapObj.on('click', function(e) {
                if (!mapClickEnabled) return;

                var lat = e.latlng.lat;
                var lng = e.latlng.lng;
                console.log('地圖點擊: ' + lat + ', ' + lng);

                // 通過 URL scheme 通知 Python
                window.location.href = 'pyqt://click/' + lat + '/' + lng;

                // 更新計數器
                cornerCount++;
                var counterEl = document.getElementById('corner-counter');
                if (counterEl) {
                    counterEl.innerHTML = '角點: ' + cornerCount + ' / ' + maxCorners;
                    if (cornerCount >= maxCorners) {
                        counterEl.style.color = '#F44336';
                    }
                }

                // 視覺反饋 - 脈衝動畫
                var marker = L.circleMarker([lat, lng], {
                    radius: 8,
                    color: '#4CAF50',
                    fillColor: '#4CAF50',
                    fillOpacity: 0.8,
                    weight: 3
                }).addTo(mapObj);

                // 脈衝效果
                var pulseRadius = 8;
                var pulseInterval = setInterval(function() {
                    pulseRadius += 2;
                    marker.setRadius(pulseRadius);
                    marker.setStyle({fillOpacity: 0.8 - (pulseRadius - 8) / 30});
                    if (pulseRadius > 25) {
                        clearInterval(pulseInterval);
                        mapObj.removeLayer(marker);
                    }
                }, 30);
            });

            // 綁定 Draw 插件事件
            mapObj.on('draw:created', function(e) {
                if (e.layer && e.layer.getLatLng) {
                    var latlng = e.layer.getLatLng();
                    console.log('Draw 標記: ' + latlng.lat + ', ' + latlng.lng);
                    window.location.href = 'pyqt://click/' + latlng.lat + '/' + latlng.lng;
                }
            });

            // 禁用拖動時的 grab 游標
            mapObj.on('mousedown', function() {
                mapObj._container.style.cursor = 'crosshair';
            });
            mapObj.on('mouseup', function() {
                mapObj._container.style.cursor = 'crosshair';
            });
            mapObj.on('mousemove', function() {
                mapObj._container.style.cursor = 'crosshair';
            });

            console.log('✅ 地圖點擊事件已綁定成功！游標模式: crosshair');
        }

        // 更新角點計數（由 Python 調用）
        function updateCornerCount(count) {
            cornerCount = count;
            var counterEl = document.getElementById('corner-counter');
            if (counterEl) {
                counterEl.innerHTML = '角點: ' + count + ' / ' + maxCorners;
                counterEl.style.color = (count >= maxCorners) ? '#F44336' : '#4CAF50';
            }
        }
        </script>
        """

        # 替換佔位符為實際的地圖變數名
        if map_var_name:
            js_code = js_code.replace('__MAP_VAR_PLACEHOLDER__', map_var_name)
        else:
            js_code = js_code.replace('__MAP_VAR_PLACEHOLDER__', 'null')

        # 在 </body> 前插入
        html = html.replace('</body>', js_code + '</body>')

        return html
    
    def add_corner(self, lat: float, lon: float) -> bool:
        """
        新增邊界點

        參數:
            lat: 緯度
            lon: 經度

        返回:
            是否成功添加
        """
        # 檢查是否達到最大角點數量
        if len(self.corners) >= MAX_CORNERS:
            logger.warning(f"已達到最大角點數量 ({MAX_CORNERS})，無法添加更多角點")
            QMessageBox.warning(
                self, "已達上限",
                f"已達到最大角點數量 ({MAX_CORNERS} 個)！\n"
                "請先刪除一些角點再添加新的。"
            )
            return False

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

        logger.info(f"新增邊界點 #{index + 1}: ({lat:.6f}, {lon:.6f}) [剩餘: {MAX_CORNERS - len(self.corners)}]")
        return True
    
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
        self.current_map.location = (settings.map.default_lat, settings.map.default_lon)
        self.current_map.zoom_start = settings.map.default_zoom
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
            if self.add_corner(lat, lon):
                self.corner_added.emit(lat, lon)
    
    def on_marker_moved(self, index: int, lat: float, lon: float):
        """處理標記移動事件"""
        self.move_corner(index, lat, lon)
        self.corner_moved.emit(index, lat, lon)

    def display_path(self, path: List[Tuple[float, float]], altitude: float = 50.0):
        """
        顯示飛行路徑

        參數:
            path: 路徑點列表 [(lat, lon), ...]
            altitude: 飛行高度（用於顯示）
        """
        if not path or len(path) < 2:
            logger.warning("路徑點不足，無法顯示")
            return

        try:
            # 清除舊路徑但保留邊界點
            self.clear_paths()

            # 繪製飛行路徑
            folium.PolyLine(
                locations=path,
                color='#08EC91',
                weight=3,
                opacity=0.8,
                popup=f'飛行路徑 (高度: {altitude}m)'
            ).add_to(self.current_map)

            # 標記起點（綠色）
            folium.Marker(
                location=path[0],
                popup=f'起點\n高度: {altitude}m',
                icon=folium.Icon(color='green', icon='play')
            ).add_to(self.current_map)

            # 標記終點（紅色）
            folium.Marker(
                location=path[-1],
                popup=f'終點\n高度: {altitude}m',
                icon=folium.Icon(color='red', icon='stop')
            ).add_to(self.current_map)

            # 標記轉折點（藍色小點）
            for i, point in enumerate(path[1:-1], start=1):
                folium.CircleMarker(
                    location=point,
                    radius=3,
                    color='#3388ff',
                    fill=True,
                    fill_color='#3388ff',
                    fill_opacity=0.7,
                    popup=f'航點 {i+1}'
                ).add_to(self.current_map)

            # 重新渲染
            self.render_map()

            # 調整視圖以包含所有點
            self.fit_bounds(path)

            logger.info(f"顯示路徑：{len(path)} 個航點")

        except Exception as e:
            logger.error(f"顯示路徑失敗: {e}")
    
    def set_edit_mode(self, enabled: bool):
        """
        設置編輯模式

        參數:
            enabled: 是否啟用編輯模式
        """
        self.edit_mode = enabled
        logger.info(f"編輯模式：{'啟用' if enabled else '停用'}")

    def get_corner_count(self) -> int:
        """獲取當前角點數量"""
        return len(self.corners)

    def get_max_corners(self) -> int:
        """獲取最大角點數量"""
        return MAX_CORNERS

    def get_remaining_corners(self) -> int:
        """獲取剩餘可添加角點數量"""
        return MAX_CORNERS - len(self.corners)

    def can_add_corner(self) -> bool:
        """檢查是否可以添加更多角點"""
        return len(self.corners) < MAX_CORNERS
    
    def closeEvent(self, event):
        """關閉事件"""
        # 清理臨時檔案
        if self.temp_html_file:
            try:
                os.unlink(self.temp_html_file)
            except:
                pass
        
        event.accept()
