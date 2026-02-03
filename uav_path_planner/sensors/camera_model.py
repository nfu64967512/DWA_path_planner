import math
import numpy as np
from dataclasses import dataclass

@dataclass
class CameraSpecs:
    """相機硬體規格資料結構"""
    sensor_width_mm: float      # 感光元件寬度 (mm)
    sensor_height_mm: float     # 感光元件高度 (mm)
    focal_length_mm: float      # 焦距 (mm)
    image_width_px: int         # 圖片寬度 (pixel)
    image_height_px: int        # 圖片高度 (pixel)
    name: str = "Generic Camera"

class CameraModel:
    """
    相機模型與視場角(FOV)計算核心
    負責計算 GSD、覆蓋範圍以及拍攝間隔
    """
    def __init__(self, specs: CameraSpecs):
        self.specs = specs
        self._validate_specs()

    def _validate_specs(self):
        if self.specs.focal_length_mm <= 0:
            raise ValueError("焦距必須大於 0")

    def calculate_fov(self) -> tuple[float, float]:
        """
        計算水平與垂直視場角 (Field of View)
        Returns:
            (hfov_deg, vfov_deg): 水平與垂直 FOV (度)
        """
        hfov = 2 * math.atan(self.specs.sensor_width_mm / (2 * self.specs.focal_length_mm))
        vfov = 2 * math.atan(self.specs.sensor_height_mm / (2 * self.specs.focal_length_mm))
        return math.degrees(hfov), math.degrees(vfov)

    def calculate_gsd(self, altitude_m: float) -> float:
        """
        計算地面採樣距離 (Ground Sampling Distance)
        Formula: (Sensor Width / Image Width) * (Altitude / Focal Length)
        
        Args:
            altitude_m: 相對地面高度 (AGL)
        Returns:
            gsd_cm_per_pixel: 每個像素代表的公分
        """
        if altitude_m <= 0:
            return 0.0
        
        # 使用感光元件寬度計算 (通常取較大邊或寬度)
        gsd_m = (self.specs.sensor_width_mm / self.specs.image_width_px) * \
                (altitude_m / (self.specs.focal_length_mm / 1000.0))
        
        return gsd_m * 100  # 轉換為 cm

    def calculate_footprint(self, altitude_m: float) -> tuple[float, float]:
        """
        計算在地面的投影範圍 (Footprint)
        
        Returns:
            (width_m, height_m): 地面覆蓋寬度與高度
        """
        if altitude_m <= 0:
            return 0.0, 0.0

        # Width on ground = (Sensor Width * Altitude) / Focal Length
        # 注意單位轉換: sensor_mm / focal_mm = 無單位比例
        width_on_ground = (self.specs.sensor_width_mm * altitude_m) / self.specs.focal_length_mm
        height_on_ground = (self.specs.sensor_height_mm * altitude_m) / self.specs.focal_length_mm
        
        return width_on_ground, height_on_ground

    def calculate_survey_parameters(self, altitude_m: float, overlap_percent: float, sidelap_percent: float):
        """
        根據重疊率計算航線參數 (供 Global Planner 使用)
        
        Args:
            overlap_percent: 航向重疊率 (Front Lap) 0-100
            sidelap_percent: 旁向重疊率 (Side Lap) 0-100
            
        Returns:
            dict: {
                'strip_distance': 航線間距 (m),
                'trigger_distance': 拍照間隔距離 (m),
                'gsd': GSD (cm/px)
            }
        """
        fp_width, fp_height = self.calculate_footprint(altitude_m)
        
        # 旁向重疊決定航線間距 (Side Lap affects distance between lines)
        # 假設 sensor width 對應橫向 (Landscape mode)
        strip_dist = fp_width * (1 - sidelap_percent / 100.0)
        
        # 航向重疊決定拍照觸發距離 (Front Lap affects trigger distance)
        trigger_dist = fp_height * (1 - overlap_percent / 100.0)
        
        return {
            "strip_distance": strip_dist,
            "trigger_distance": trigger_dist,
            "gsd": self.calculate_gsd(altitude_m),
            "footprint_width": fp_width,
            "footprint_height": fp_height
        }

# 範例：定義一個常見的相機 (如 Sony RX1R II)
RX1R_II = CameraSpecs(
    sensor_width_mm=35.9,
    sensor_height_mm=24.0,
    focal_length_mm=35.0,
    image_width_px=7952,
    image_height_px=5304,
    name="Sony RX1R II"
)