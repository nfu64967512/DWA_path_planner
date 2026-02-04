import os

# 設定要讀取的檔案副檔名，根據您的專案需求調整
TARGET_EXTENSIONS = {'.py', '.md', '.txt', '.yaml', '.xml', '.launch', '.json'}
# 設定要忽略的目錄
IGNORE_DIRS = {'.git', '__pycache__', 'venv', 'build', 'devel', '.idea', '.vscode'}

def merge_project_files(output_file='project_context.txt'):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        # 1. 先寫入目錄結構樹 (Tree Structure)
        outfile.write("=== PROJECT STRUCTURE ===\n")
        for root, dirs, files in os.walk('.'):
            # 過濾忽略的目錄
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            level = root.replace('.', '').count(os.sep)
            indent = ' ' * 4 * (level)
            outfile.write(f"{indent}{os.path.basename(root)}/\n")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                outfile.write(f"{subindent}{f}\n")
        
        outfile.write("\n\n=== FILE CONTENTS ===\n")
        
        # 2. 寫入檔案內容
        for root, dirs, files in os.walk('.'):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext in TARGET_EXTENSIONS:
                    file_path = os.path.join(root, file)
                    outfile.write(f"\n\n--- START OF FILE: {file_path} ---\n")
                    try:
                        with open(file_path, 'r', encoding='utf-8') as infile:
                            outfile.write(infile.read())
                    except Exception as e:
                        outfile.write(f"Error reading file: {e}")
                    outfile.write(f"\n--- END OF FILE: {file_path} ---\n")

    print(f"專案已整合至 {output_file}，請將該檔案內容傳送給我。")

if __name__ == "__main__":
    merge_project_files()