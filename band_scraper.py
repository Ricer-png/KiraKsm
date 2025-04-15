import os
import io
import re
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from pydub import AudioSegment
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from get_path import resource_path

class BestdoriScraperBand:
    def __init__(self, target_name, log_queue, progress_queue, stop_flag, wav_flag):
        self.target_name = target_name
        self.log_queue = log_queue
        self.progress_queue = progress_queue
        self.stop_flag = stop_flag
        self.wav_flag = wav_flag
        self.kyara_name = self.get_character_names()
        self.log_data = {}
        self.band_url = "https://bestdori.com/tool/storyviewer"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UserAgent().random})
        if self.kyara_name:
            self.save_folder = os.path.join(os.getcwd(), self.kyara_name[2])
            self.save_card_audio_folder = os.path.join(self.save_folder, f"{self.kyara_name[2]}_mp3")
            self.save_wav_folder = os.path.join(self.save_folder, f"{self.kyara_name[2]}_wav")

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

    def setup_browser(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        driver = webdriver.Chrome(options=options)
        driver.get(self.band_url)
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        return driver
    
    # 选择日服服务器
    def select_jp_server(self, driver):
        try:
            server_button = driver.find_element(By.XPATH, "//a[contains(@class, 'button is-rounded round') and .//img[contains(@alt, 'JP')]]")
            if "is-focused" not in server_button.get_attribute("class"):
                server_button.click()
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'button') and .//i[contains(@class, 'fas fa-times')]]"))).click()
        except Exception as e:
            self.log_queue.put(f"服务器选择失败: {e}")
        time.sleep(0.4)

    # 故事id
    def exetract_band_story_ids(self, driver):
        # band story
        band_story_tab = driver.find_element(By.XPATH, "//a[contains(text(), 'Band Story')]")
        band_story_tab.click()
        time.sleep(0.4)

        # select band
        band_button = driver.find_element(By.XPATH, f"//a[contains(@class, 'button is-rounded round') and .//img[contains(@alt, '{self.kyara_name[3]}')]]")
        if "is-focused" not in band_button.get_attribute("class"):
            band_button.click()
        time.sleep(0.4)

        #select chapter
        select_element = driver.find_element(By.XPATH, "//select[@data-v-24b49681]")
        select = Select(select_element)
        options = select.options
        band_story_IDs = []
        for option in options:
            value = option.get_attribute("value")
            if value == "0":  # 忽略默认选项
                continue

            select.select_by_value(value)
            time.sleep(0.4)
            page_source = driver.page_source
            band_story_IDs += re.findall(r'/tool/storyviewer/band/jp/(\d+)(?:/|$)', page_source)

        return band_story_IDs

    def load_log(self):
        log_path = os.path.join(self.save_folder, "log_band.json")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_log(self):
        log_path = os.path.join(self.save_folder, "log_band.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self.log_data, f, indent=4, ensure_ascii=False)
    
    # 下载音频
    def download_audio(self, audio_url, save_path):
        try:
            response = self.session.get(audio_url, stream=True, timeout=10)
            response.raise_for_status()
            if self.wav_flag.is_set():
                # 载入pydub
                mp3_data = io.BytesIO()
                for chunk in response.iter_content(1024):
                    mp3_data.write(chunk)
                mp3_data.seek(0)
                # 流式转换为 WAV 16kHz, 单声道, 16-bit
                audio = AudioSegment.from_file(mp3_data, format="mp3")
                audio = audio.set_frame_rate(16000).set_channels(1)
                audio.export(save_path, format="wav", codec="pcm_s16le")
            else:  # mp3
                with open(save_path, "wb") as file:
                    for chunk in response.iter_content(1024):
                        file.write(chunk)

            self.log_queue.put(f"下载成功: {save_path}")

        except requests.exceptions.RequestException as e:
            self.log_queue.put(f"下载失败: {audio_url}, 错误: {e}")

    def scrape_card_audio(self, driver, card_ID):
        driver.get(f"https://bestdori.com/tool/storyviewer/band/jp/{card_ID}")
        WebDriverWait(driver, 5).until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(1.14)

        try:
            list_button = driver.find_element(By.XPATH, "//a[contains(@class, 'button is-rounded round') and .//i[contains(@class, 'fa-bars')]]")
            if "is-focused" not in list_button.get_attribute("class"):
                list_button.click()
        except:
            return
        time.sleep(1.14)

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        dialogue_blocks = soup.find_all("a", class_="box bg-white download-container")

        for block in dialogue_blocks:
            name_tag = block.find("div", class_="m-b-xs fg-text")
            name = name_tag.find_all("span")[-1].text.strip() if name_tag else "???"

            if name in self.kyara_name:
                dialogue_tags = block.find_all("div", class_="column")
                dialogue = next((tag.text.strip() for tag in dialogue_tags if tag.text.strip()), "")
                dialogue = dialogue.replace("\n", "")

                if len(dialogue) < 5:
                    continue

                audio_tag = block.find("a", class_="button is-small", href=True)
                audio_url = "https://bestdori.com" + audio_tag["href"] if audio_tag else "无"

                if audio_url:
                    file_name = re.sub(r'[\/:*?"<>|]', '', dialogue)
                    if self.wav_flag.is_set():
                        file_path = os.path.join(self.save_wav_folder, f"{file_name}.wav")
                    else:
                        file_path = os.path.join(self.save_card_audio_folder, f"{file_name}.mp3")
                    self.download_audio(audio_url, file_path)

            if self.stop_flag.is_set():
                driver.quit()
                exit()
        
        self.log_data[card_ID] = True  # 标记为已下载
        self.save_log()

    def start_scraping(self):
        if not self.kyara_name:
            return
        
        os.makedirs(self.save_folder, exist_ok=True)
        if self.wav_flag.is_set():
            os.makedirs(self.save_wav_folder, exist_ok=True)
            self.log_queue.put(f"开始收集 {self.kyara_name[1]} .wav格式乐队故事语音数据...")
        else:
            os.makedirs(self.save_card_audio_folder, exist_ok=True)
            self.log_queue.put(f"开始收集 {self.kyara_name[1]} .mp3格式乐队故事语音数据...")

        driver = self.setup_browser()
        self.select_jp_server(driver)
        if self.stop_flag.is_set():
            driver.quit()
            exit()

        self.log_data = self.load_log()
        if not self.log_data:
            card_IDs = self.exetract_band_story_ids(driver)
            for card_ID in card_IDs:
                self.log_data.setdefault(card_ID, False)
            self.save_log()
        else:
            card_IDs = [card_id for card_id, status in self.log_data.items() if not status]
        
        if card_IDs:
            # 进度条
            completed = len([card_id for card_id, status in self.log_data.items() if status])
            self.progress_queue.put(completed / len([card_id for card_id in self.log_data.items()]))

            for card_ID in card_IDs:
                # 调用单张爬取
                self.scrape_card_audio(driver, card_ID)
                # 更新进度条
                completed = len([card_id for card_id, status in self.log_data.items() if status])
                self.progress_queue.put(completed / len([card_id for card_id in self.log_data.items()]))

            driver.quit()
            self.log_queue.put(f"已成功收集 {self.kyara_name[1]} 所有乐队故事语音")
        else:
            self.log_queue.put(f"未找到 {self.kyara_name[1]} 有关的乐队故事音频数据")
            driver.quit()
            exit()

def run_scraper_band(target_name, log_queue, progress_queue, stop_flag, wav_flag):
    scraper = BestdoriScraperBand(target_name, log_queue, progress_queue, stop_flag, wav_flag)
    scraper.start_scraping()
