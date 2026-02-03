"""
覆蓋路徑規劃器
用於生成完全覆蓋指定區域的掃描路徑
支持網格掃描、螺旋掃描等多種模式
"""

import math
from enum import Enum
from typing import List, Tuple, Optional
from dataclasses import dataclass

from ..geometry import RotatedCoordinateSystem, CoordinateTransform
from ..collision import CollisionChecker


class ScanPattern(Enum):
    """掃描模式"""
    GRID = "grid"          # 網格掃描（之字形）
    SPIRAL = "spiral"      # 螺旋掃描
    CIRCULAR = "circular"  # 圓形掃描
    FILL = "fill"          # 填充掃描


@dataclass
class CoverageParameters:
    """覆蓋參數"""
    spacing: float          # 掃描線間距（公尺）
    angle: float           # 掃描角度（度）
    pattern: ScanPattern = ScanPattern.GRID
    overlap: float = 0.1   # 重疊率（0-1）
    start_from_corner: bool = True  # 是否從角落開始


class CoveragePlanner:
    """覆蓋路徑規劃器"""
    
    def __init__(self, 
                 collision_checker: Optional[CollisionChecker] = None):
        """
        初始化覆蓋規劃器
        
        參數:
            collision_checker: 碰撞檢測器（可選）
        """
        self.collision_checker = collision_checker
    
    def plan_coverage(self,
                     polygon: List[Tuple[float, float]],
                     params: CoverageParameters) -> List[Tuple[float, float]]:
        """
        規劃覆蓋路徑
        
        參數:
            polygon: 多邊形區域（經緯度）
            params: 覆蓋參數
        
        返回:
            覆蓋路徑點列表
        """
        if params.pattern == ScanPattern.GRID:
            return self._plan_grid_coverage(polygon, params)
        elif params.pattern == ScanPattern.SPIRAL:
            return self._plan_spiral_coverage(polygon, params)
        else:
            raise ValueError(f"不支持的掃描模式: {params.pattern}")
    
    def _plan_grid_coverage(self,
                          polygon: List[Tuple[float, float]],
                          params: CoverageParameters) -> List[Tuple[float, float]]:
        """
        網格掃描路徑規劃
        
        參數:
            polygon: 多邊形區域
            params: 覆蓋參數
        
        返回:
            掃描路徑點列表
        """
        # 計算多邊形中心
        center_lat = sum(p[0] for p in polygon) / len(polygon)
        center_lon = sum(p[1] for p in polygon) / len(polygon)
        
        # 創建旋轉座標系
        rotated_system = RotatedCoordinateSystem(
            center_lat, center_lon, params.angle
        )
        
        # 將多邊形轉換到旋轉座標系
        rotated_polygon = rotated_system.batch_latlon_to_xy(polygon)
        
        # 計算掃描線
        path_rotated = self._generate_scan_lines(rotated_polygon, params.spacing)
        
        # 轉換回經緯度
        path = rotated_system.batch_xy_to_latlon(path_rotated)
        
        # 應用碰撞檢測（如果有）
        if self.collision_checker:
            path = self._filter_collision_points(path)
        
        return path
    
    def _generate_scan_lines(self,
                           polygon: List[Tuple[float, float]],
                           spacing: float) -> List[Tuple[float, float]]:
        """
        生成掃描線（之字形）
        
        參數:
            polygon: 旋轉座標系中的多邊形
            spacing: 掃描線間距
        
        返回:
            掃描路徑點
        """
        # 計算邊界
        ys = [p[1] for p in polygon]
        min_y = min(ys)
        max_y = max(ys)
        
        # 計算掃描線數量
        num_lines = int((max_y - min_y) / spacing) + 1
        
        path = []
        
        for i in range(num_lines):
            y = min_y + i * spacing
            
            # 計算與多邊形的交點
            intersections = self._find_line_polygon_intersections(polygon, y)
            
            if len(intersections) < 2:
                continue
            
            # 排序交點
            intersections.sort()
            
            # 之字形路徑：奇數行從左到右，偶數行從右到左
            if i % 2 == 0:
                path.append((intersections[0], y))
                path.append((intersections[-1], y))
            else:
                path.append((intersections[-1], y))
                path.append((intersections[0], y))
        
        return path
    
    def _find_line_polygon_intersections(self,
                                       polygon: List[Tuple[float, float]],
                                       y: float) -> List[float]:
        """
        計算水平線與多邊形的交點
        
        參數:
            polygon: 多邊形頂點
            y: 水平線的y座標
        
        返回:
            交點的x座標列表
        """
        intersections = []
        n = len(polygon)
        
        for i in range(n):
            p1 = polygon[i]
            p2 = polygon[(i + 1) % n]
            
            # 檢查線段是否與水平線相交
            if (p1[1] <= y <= p2[1]) or (p2[1] <= y <= p1[1]):
                if abs(p2[1] - p1[1]) > 1e-10:
                    # 計算交點的x座標
                    t = (y - p1[1]) / (p2[1] - p1[1])
                    x = p1[0] + t * (p2[0] - p1[0])
                    intersections.append(x)
        
        return intersections
    
    def _plan_spiral_coverage(self,
                            polygon: List[Tuple[float, float]],
                            params: CoverageParameters) -> List[Tuple[float, float]]:
        """
        螺旋掃描路徑規劃
        
        參數:
            polygon: 多邊形區域
            params: 覆蓋參數
        
        返回:
            螺旋路徑點列表
        """
        # 計算多邊形中心和半徑
        center_lat = sum(p[0] for p in polygon) / len(polygon)
        center_lon = sum(p[1] for p in polygon) / len(polygon)
        
        # 轉換到平面座標
        coord_transform = CoordinateTransform(center_lat, center_lon)
        polygon_xy = coord_transform.batch_latlon_to_xy(polygon)
        
        # 計算最大半徑
        max_radius = max(
            math.sqrt(p[0]**2 + p[1]**2) for p in polygon_xy
        )
        
        # 生成螺旋路徑
        path_xy = []
        radius = 0.0
        angle = 0.0
        angular_step = math.radians(10)  # 10度步進
        
        while radius < max_radius:
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            
            # 檢查是否在多邊形內
            if self._point_in_polygon((x, y), polygon_xy):
                path_xy.append((x, y))
            
            # 更新
            angle += angular_step
            radius += params.spacing / (2 * math.pi)  # 每轉一圈增加spacing
        
        # 轉換回經緯度
        path = coord_transform.batch_xy_to_latlon(path_xy)
        
        return path
    
    def _point_in_polygon(self, 
                         point: Tuple[float, float],
                         polygon: List[Tuple[float, float]]) -> bool:
        """
        判斷點是否在多邊形內（射線法）
        
        參數:
            point: 點座標
            polygon: 多邊形頂點
        
        返回:
            是否在多邊形內
        """
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def _filter_collision_points(self,
                                path: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        過濾掉與障礙物碰撞的點
        
        參數:
            path: 原始路徑
        
        返回:
            過濾後的路徑
        """
        if not self.collision_checker:
            return path
        
        filtered_path = []
        
        for point in path:
            if not self.collision_checker.check_point_collision(point):
                filtered_path.append(point)
        
        return filtered_path
    
    def calculate_coverage_area(self,
                               polygon: List[Tuple[float, float]]) -> float:
        """
        計算多邊形面積（平方公尺）
        
        參數:
            polygon: 多邊形頂點（經緯度）
        
        返回:
            面積（平方公尺）
        """
        if len(polygon) < 3:
            return 0.0
        
        # 轉換到平面座標
        center_lat = sum(p[0] for p in polygon) / len(polygon)
        center_lon = sum(p[1] for p in polygon) / len(polygon)
        coord_transform = CoordinateTransform(center_lat, center_lon)
        polygon_xy = coord_transform.batch_latlon_to_xy(polygon)
        
        # 使用Shoelace公式計算面積
        area = 0.0
        n = len(polygon_xy)
        
        for i in range(n):
            j = (i + 1) % n
            area += polygon_xy[i][0] * polygon_xy[j][1]
            area -= polygon_xy[j][0] * polygon_xy[i][1]
        
        return abs(area) / 2.0
    
    def estimate_mission_time(self,
                            path: List[Tuple[float, float]],
                            speed: float) -> float:
        """
        估算任務時間
        
        參數:
            path: 路徑點列表
            speed: 飛行速度（公尺/秒）
        
        返回:
            預估時間（秒）
        """
        if len(path) < 2 or speed <= 0:
            return 0.0
        
        total_distance = 0.0
        
        for i in range(len(path) - 1):
            lat1, lon1 = path[i]
            lat2, lon2 = path[i + 1]
            
            # 使用簡化距離計算
            dlat = (lat2 - lat1) * 111111.0
            dlon = (lon2 - lon1) * 111111.0 * math.cos(math.radians((lat1 + lat2) / 2))
            distance = math.sqrt(dlat**2 + dlon**2)
            
            total_distance += distance
        
        return total_distance / speed


def optimize_scan_angle(polygon: List[Tuple[float, float]],
                       spacing: float,
                       angle_step: float = 5.0) -> float:
    """
    優化掃描角度（最小化掃描線數量）
    
    參數:
        polygon: 多邊形區域
        spacing: 掃描線間距
        angle_step: 角度步進（度）
    
    返回:
        最優掃描角度（度）
    """
    planner = CoveragePlanner()
    min_length = float('inf')
    best_angle = 0.0
    
    # 嘗試不同角度
    for angle in range(0, 180, int(angle_step)):
        params = CoverageParameters(
            spacing=spacing,
            angle=angle,
            pattern=ScanPattern.GRID
        )
        
        path = planner.plan_coverage(polygon, params)
        
        # 計算路徑長度
        if len(path) > 1:
            length = sum(
                math.sqrt((path[i+1][0] - path[i][0])**2 + (path[i+1][1] - path[i][1])**2)
                for i in range(len(path) - 1)
            )
            
            if length < min_length:
                min_length = length
                best_angle = angle
    
    return best_angle
