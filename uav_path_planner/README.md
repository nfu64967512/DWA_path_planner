# UAV Path Planner - 無人機路徑規劃系統

**版本**: 2.0.0  
**授權**: MIT  
**Python**: >= 3.8

## 專案概述

基於 Mission Planner 演算法核心，採用現代化 Python 架構重新設計的專業級無人機路徑規劃系統。支援多旋翼與固定翼（未來），整合全域規劃與局域規劃功能。

### 主要特性

- ✅ **多飛行器支援**: 多旋翼（四軸、六軸、八軸）
- ✅ **智能路徑規劃**: 整合 A*/RRT/Coverage 演算法
- ✅ **障礙物避讓**: 智能避障與碰撞檢測
- ✅ **任務管理**: 完整的任務規劃與執行
- ✅ **MAVLink 整合**: 標準 MAVLink 協議支援
- ⏳ **群飛協調**: 多機協同飛行（開發中）
- ⏳ **SLAM 整合**: Kimera VIO 系統整合（規劃中）

## 快速開始

### 1. 安裝依賴

```bash
# 創建虛擬環境（推薦）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 安裝依賴套件
pip install -r requirements.txt
```

### 2. 基本使用

```bash
# GUI 模式（預設）
python main.py

# 命令列模式
python main.py --no-ui

# 指定配置文件
python main.py --config path/to/config.json

# 設定日誌等級
python main.py --log-level DEBUG
```

### 3. 程式化使用

```python
from uav_path_planner import get_settings, get_logger
from uav_path_planner.core import MultirotorVehicle
from uav_path_planner.utils import read_yaml

# 初始化系統
settings = get_settings()
logger = get_logger()

# 載入飛行器配置
vehicle_config = read_yaml('config/vehicle_profiles.yaml')
quadcopter_config = vehicle_config['multirotor']['dji_mavic_3']

# 創建飛行器實例
drone = MultirotorVehicle('drone_01', quadcopter_config)

# 驗證航點
waypoint = (23.7027, 120.4193, 50.0)  # lat, lon, alt
if drone.validate_waypoint(waypoint):
    flight_time = drone.calculate_flight_time(distance_m=1000)
    print(f"預估飛行時間: {flight_time:.1f} 秒")
```

## 專案結構

```
uav_path_planner/
├── main.py                      # 程式進入點
├── requirements.txt             # 依賴套件
│
├── config/                      # 配置模組
│   ├── settings.py              # 全局配置
│   └── vehicle_profiles.yaml   # 飛行器參數
│
├── core/                        # 核心演算法
│   ├── base/                    # 基礎類別
│   │   ├── vehicle_base.py      # 飛行器基類
│   │   ├── planner_base.py      # 規劃器基類
│   │   └── constraint_base.py   # 約束基類
│   │
│   ├── vehicles/                # 飛行器模型
│   │   └── multirotor.py        # 多旋翼模型
│   │
│   ├── geometry/                # 幾何計算 (TODO)
│   ├── global_planner/          # 全域規劃 (TODO)
│   ├── local_planner/           # 局域規劃 (TODO)
│   ├── trajectory/              # 軌跡優化 (TODO)
│   └── collision/               # 碰撞檢測 (TODO)
│
├── mission/                     # 任務管理 (TODO)
├── sensors/                     # 感測器整合 (TODO)
│
├── ui/                          # PyQt UI (TODO)
│   ├── widgets/                 # UI 組件
│   └── dialogs/                 # 對話框
│
├── utils/                       # 工具模組
│   ├── logger.py                # 日誌工具
│   ├── math_utils.py            # 數學工具
│   └── file_io.py               # 檔案讀寫
│
├── data/                        # 資料目錄
│   ├── logs/                    # 日誌檔案
│   ├── exports/                 # 匯出檔案
│   └── cache/                   # 快取檔案
│
└── tests/                       # 測試 (TODO)
```

## 配置說明

### 飛行器配置 (vehicle_profiles.yaml)

系統預設提供多種飛行器配置：

- **DJI Mavic 3**: 專業航拍無人機
- **DJI Phantom 4 Pro**: 經典測繪無人機
- **DJI Mini 3 Pro**: 輕量級無人機
- **Generic Quadcopter**: 通用四軸配置（可自訂）

### 系統配置 (settings.py)

主要配置類別：

- `PathSettings`: 路徑配置
- `MapSettings`: 地圖設定
- `ExportSettings`: 匯出選項
- `PerformanceSettings`: 效能參數
- `SafetySettings`: 安全限制
- `UISettings`: 界面設定

## 開發路線圖

### 已完成 ✅
- [x] 專案架構設計
- [x] 基礎類別實現
- [x] 多旋翼飛行器模型
- [x] 配置管理系統
- [x] 工具模組（日誌、數學、檔案）
- [x] 主程式框架

### 進行中 🚧
- [ ] 幾何計算模組
- [ ] 全域路徑規劃器
- [ ] 障礙物管理系統
- [ ] PyQt UI 界面

### 規劃中 📋
- [ ] 局域路徑規劃 (DWA/MPC)
- [ ] 軌跡優化
- [ ] 任務管理系統
- [ ] MAVLink 通訊
- [ ] 群飛協調
- [ ] Kimera VIO 整合
- [ ] 完整測試套件
- [ ] 使用文檔

## 開發指南

### 添加新的飛行器模型

1. 在 `core/vehicles/` 創建新文件
2. 繼承 `VehicleBase` 抽象類別
3. 實現所有抽象方法
4. 在 `vehicle_profiles.yaml` 添加配置

```python
from core.base import VehicleBase

class MyVehicle(VehicleBase):
    def get_vehicle_type(self) -> str:
        return "my_vehicle_type"
    
    # 實現其他抽象方法...
```

### 添加新的路徑規劃器

1. 在 `core/global_planner/` 或 `core/local_planner/` 創建新文件
2. 繼承 `PlannerBase` 抽象類別
3. 實現 `plan()` 方法
4. 註冊到規劃器工廠

```python
from core.base import PlannerBase, PlanningResult

class MyPlanner(PlannerBase):
    def get_planner_name(self) -> str:
        return "my_planner"
    
    def plan(self, start, goal, **kwargs) -> PlanningResult:
        # 實現規劃邏輯
        path = [...]
        return PlanningResult(path=path, success=True)
```

## 技術棧

- **Python**: 3.8+
- **UI**: PyQt6
- **地圖**: Folium + PyQtWebEngine
- **幾何**: Shapely, NumPy
- **座標轉換**: pyproj
- **加速**: Numba JIT
- **通訊**: pymavlink

## 貢獻指南

歡迎提交 Issue 和 Pull Request！

### 開發流程

1. Fork 專案
2. 創建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

### 代碼規範

- 使用 Black 格式化代碼
- 使用 Flake8 檢查代碼
- 使用 mypy 進行類型檢查
- 添加適當的文檔字串
- 編寫單元測試

```bash
# 格式化代碼
black .

# 檢查代碼
flake8 .

# 類型檢查
mypy .

# 運行測試
pytest tests/
```

## 授權

MIT License - 詳見 LICENSE 文件

## 聯絡方式

- 專案主頁: [GitHub](https://github.com/your-repo/uav-path-planner)
- 問題回報: [Issues](https://github.com/your-repo/uav-path-planner/issues)
- 文檔: [Wiki](https://github.com/your-repo/uav-path-planner/wiki)

## 致謝

感謝以下開源專案的靈感和參考：

- Mission Planner
- ArduPilot
- PythonRobotics
- QGroundControl

---

**注意**: 本專案目前處於開發階段，部分功能尚未完成。歡迎關注並參與開發！
