import os
import shutil

def separate_files(prefix, path, log_queue):
    if not os.path.isdir(path):
        log_queue.put(f"错误：路径 '{path}' 不存在")
        return

    for filename in os.listdir(path):
        if not filename.startswith(f"{prefix}_"):
            continue

        parts = filename.split('_', 1)
        if len(parts) != 2 or not parts[1].strip():
            log_queue.put(f"存在特殊格式的文件 '{filename}' 请手动分离")
            continue

        origin_path = os.path.join(path, filename)
        if not os.path.isfile(origin_path):
            continue
  
        new_name = parts[1].strip()
        target_dir = os.path.join(path, prefix)
        
        try:
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, new_name)
            
            # 移动并重命名文件
            shutil.move(origin_path, target_path)
        except Exception as e:
            log_queue.put(f"移动文件 '{filename}' 失败：{str(e)}")
            continue
        
    log_queue.put("done")
