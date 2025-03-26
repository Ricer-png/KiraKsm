import os
import json
from get_path import resource_path

class Audio2List:
    def __init__(self, target_name, log_queue, target_path, wav_flag):
        self.target_name = target_name
        self.log_queue = log_queue
        self.wav_flag = wav_flag
        self.kyara_name = self.get_character_names()

        if self.kyara_name:
            self.save_folder = os.path.join(os.getcwd(), self.kyara_name[2])
            if self.wav_flag.is_set():
                self.save_audio_folder = os.path.join(self.save_folder, f"{self.kyara_name[2]}_wav")
            else:
                self.save_audio_folder = os.path.join(self.save_folder, f"{self.kyara_name[2]}_mp3")

        if target_path:
            self.target_path = target_path
        else:
            self.target_path = self.save_audio_folder

    def get_character_names(self):
            try:
                with open(resource_path("characters.json"), "r", encoding="utf-8") as f:
                    character_map = json.load(f)
                kyara_name = character_map.get(self.target_name, [])
                if not kyara_name:
                    self.log_queue.put(f"未找到 {self.target_name} 对应的角色, 请输入常见的昵称。(如:户山香澄、香澄、香橙、ksm、邦高祖、cdd)")
                    return None
                return kyara_name
            except FileNotFoundError:
                self.log_queue.put("错误: 未找到角色映射文件 characters.json")
                return None

    def audio_to_list(self):
        if self.wav_flag.is_set():
            audio_files = [f for f in os.listdir(self.save_audio_folder) if f.endswith(".wav")]
            index_path = os.path.join(self.save_folder, f'{self.kyara_name[2]}_wav.list')
        else:
            audio_files = [f for f in os.listdir(self.save_audio_folder) if f.endswith(".mp3")]
            index_path = os.path.join(self.save_folder, f'{self.kyara_name[2]}_mp3.list')
        with open(index_path, "w", encoding="utf-8") as f:
            for mp3_file in audio_files:
                # 获取文件名（含后缀）和不含后缀的文件名
                file_with_extension = mp3_file
                file_without_extension = os.path.splitext(mp3_file)[0]
                file_path = os.path.join(self.target_path, file_with_extension)
                # 构造索引内容
                index_content = f"{file_path}|{self.kyara_name[2]}|JA|{file_without_extension}\n"
                
                # 写入索引内容到文件
                f.write(index_content)

        self.log_queue.put(f"索引文件已生成, 索引文件路径:\n{index_path}\n资源文件夹路径:\n{self.save_audio_folder}\n目标路径:\n{self.target_path}")

def run_A_to_Z(target_name, log_queue, target_path, wav_flag):
    maruyama = Audio2List(target_name, log_queue, target_path, wav_flag)
    maruyama.audio_to_list()