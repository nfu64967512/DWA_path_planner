"""
UAV Path Planner - 主程式入口
無人機路徑規劃系統
"""

import sys
import argparse
from pathlib import Path

# 添加專案根目錄到路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import init_settings, get_settings
from utils import get_logger, setup_logger


def parse_arguments():
    """解析命令列參數"""
    parser = argparse.ArgumentParser(
        description='UAV Path Planner - 無人機路徑規劃系統',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='配置文件路徑'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='日誌等級'
    )
    
    parser.add_argument(
        '--no-ui',
        action='store_true',
        help='無界面模式（僅命令列）'
    )
    
    parser.add_argument(
        '--vehicle',
        type=str,
        default='generic_quadcopter',
        help='飛行器配置檔案名稱'
    )
    
    return parser.parse_args()


def initialize_system(args):
    """初始化系統"""
    # 初始化日誌
    logger = setup_logger(
        name='UAVPathPlanner',
        level=args.log_level,
        log_to_file=True,
        log_to_console=True
    )
    
    logger.info("=" * 60)
    logger.info("UAV Path Planner 啟動")
    logger.info("版本: 2.0.0")
    logger.info("=" * 60)
    
    # 初始化配置
    settings = init_settings(args.config)
    logger.info(f"配置文件: {args.config or '使用預設配置'}")
    
    # 載入飛行器配置
    from config.settings import get_settings
    from utils.file_io import read_yaml
    import os
    
    vehicle_config_path = os.path.join(
        settings.paths.config_dir,
        'vehicle_profiles.yaml'
    )
    
    if os.path.exists(vehicle_config_path):
        vehicle_profiles = read_yaml(vehicle_config_path)
        logger.info(f"飛行器配置載入成功: {len(vehicle_profiles or {})} 種類型")
    else:
        logger.warning(f"飛行器配置文件不存在: {vehicle_config_path}")
        vehicle_profiles = None
    
    return logger, settings, vehicle_profiles


def run_gui_mode(logger, settings, vehicle_profiles):
    """運行GUI模式"""
    try:
        logger.info("啟動 GUI 模式...")
        
        # 檢查PyQt6是否可用
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import Qt
        except ImportError:
            logger.error("PyQt6 未安裝，無法啟動 GUI 模式")
            logger.info("請安裝: pip install PyQt6 PyQt6-WebEngine")
            return 1
        
        # 創建應用程式
        app = QApplication(sys.argv)
        app.setApplicationName("UAV Path Planner")
        app.setOrganizationName("UAV Team")
        
        # PyQt6 已默認啟用高DPI支持，移除以下設置
        # app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        # app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
        # 導入主視窗 (TODO: 實現 UI 模組後取消註解)
        # from ui.main_window import MainWindow
        # window = MainWindow(settings, vehicle_profiles)
        # window.show()
        
        logger.info("GUI 啟動成功")
        logger.warning("注意: UI 模組尚未實現，暫時顯示空白視窗")
        
        # TODO: 移除這段臨時代碼
        from PyQt6.QtWidgets import QMainWindow, QLabel
        from PyQt6.QtCore import Qt as QtCore
        
        class TempWindow(QMainWindow):
            def __init__(self):
                super().__init__()
                self.setWindowTitle("UAV Path Planner - 開發中")
                self.setGeometry(100, 100, 1200, 800)
                label = QLabel("UAV Path Planner v2.0\n\n核心系統已建立\nUI 模組開發中...", self)
                label.setAlignment(QtCore.AlignmentFlag.AlignCenter)
                label.setStyleSheet("font-size: 24px; color: #2196F3;")
                self.setCentralWidget(label)
        
        window = TempWindow()
        window.show()
        
        return app.exec()
    
    except Exception as e:
        # 移除 exc_info 參數
        logger.error(f"GUI 啟動失敗: {e}")
        import traceback
        traceback.print_exc()  # 直接打印堆疊追蹤
        return 1


def main():
    """主函式"""
    # 解析參數
    args = parse_arguments()
    
    # 初始化系統
    try:
        logger, settings, vehicle_profiles = initialize_system(args)
    except Exception as e:
        print(f"系統初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 選擇運行模式
    try:
        if args.no_ui:
            return run_cli_mode(logger, settings, vehicle_profiles)
        else:
            return run_gui_mode(logger, settings, vehicle_profiles)
    
    except KeyboardInterrupt:
        logger.info("用戶中斷程式")
        return 0
    
    except Exception as e:
        # 移除 exc_info 參數
        logger.error(f"程式異常終止: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        logger.info("UAV Path Planner 已退出")


if __name__ == '__main__':
    sys.exit(main())
