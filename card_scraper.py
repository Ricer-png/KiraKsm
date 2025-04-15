import os
import io
import re
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from pydub import AudioSegment
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from get_path import resource_path

class BestdoriScraper:
    def __init__(self, target_name, log_queue, progress_queue, stop_flag, wav_flag):
        self.target_name = target_name
        self.log_queue = log_queue
        self.progress_queue = progress_queue
        self.stop_flag = stop_flag
        self.wav_flag = wav_flag
        self.kyara_name = self.get_character_names()
        self.log_data = {}
        self.card_url = "https://bestdori.com/info/cards"
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
        driver.get(self.card_url)
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        return driver
    
    # 选择日服服务器
    def select_jp_server(self, driver):
        try:
            server_button = driver.find_element(By.XPATH, "//a[contains(@class, 'button is-rounded round') and .//img[contains(@alt, 'JP')]]")
            if "is-focused" not in server_button.get_attribute("class"):
                server_button.click()
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'button') and .//i[contains(@class, 'fas fa-times')]]"))).click()
        except Exception as e:
            self.log_queue.put(f"服务器选择失败: {e}")
        time.sleep(0.4)

    # 选择角色
    def select_character(self, driver):
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'button') and .//i[contains(@class, 'fa-filter')]]"))).click()
        time.sleep(0.4)

        actions = ActionChains(driver)
        all_kyara_button = driver.find_element(By.XPATH, "//div[@class='field max-width-40']/div[@class='control']/div[@class='buttons']/a[contains(@class, 'button-all')]")
        actions.move_to_element(all_kyara_button).click().perform()
        time.sleep(0.4)

        kyara_button = driver.find_element(By.XPATH, f"//a[contains(@class, 'button is-rounded round') and .//img[contains(@alt, '{self.kyara_name[0]}')]]")
        kyara_button.click()
        time.sleep(0.4)

    # 获取所有卡片 ID
    def extract_card_ids(self, driver):
        card_list_button = driver.find_element(By.XPATH, "//a[contains(@class, 'button is-rounded round') and .//i[contains(@class, 'fas fa-grip-horizontal')]]")
        if "is-focused" not in card_list_button.get_attribute("class"):
            card_list_button.click()
        time.sleep(0.4)
        while True:
            try:
                show_more_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'button is-fullwidth')]")))
                driver.execute_script("arguments[0].scrollIntoView(true);", show_more_button)
                show_more_button.click()
                time.sleep(0.4)
            except:
                break

        page_source = driver.page_source
        return re.findall(r'/info/cards/(\d+)(?:/|$)', page_source)

    def load_log(self):
        log_path = os.path.join(self.save_folder, "log.json")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_log(self):
        log_path = os.path.join(self.save_folder, "log.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self.log_data, f, indent=4, ensure_ascii=False)
    
    # 处理文本
    def clean_dialogue(self, dialogue):
        dialogue = dialogue.replace("\n", "")
        temp_pattern = r"([、と])?(New Staffさん(?:も|は|が|に|を|の|と)?)([。、？！]?)"
        dialogue = re.sub(temp_pattern, lambda match: "。" if match.group(1) else "", dialogue)
        return dialogue
    
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
        for i in [2, 1]:
            driver.get(f"https://bestdori.com/tool/storyviewer/card/jp/{card_ID}/{i}")
            WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            time.sleep(1.14)

            try:
                list_button = driver.find_element(By.XPATH, "//a[contains(@class, 'button is-rounded round') and .//i[contains(@class, 'fa-bars')]]")
                if "is-focused" not in list_button.get_attribute("class"):
                    list_button.click()
            except:
                self.log_queue.put(f"ID{card_ID}:该卡片没有对应故事")
                self.log_data.pop(card_ID, None)  # 无故事则删除 ID
                self.save_log()
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
                    dialogue = self.clean_dialogue(dialogue)

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
            
            self.log_data[card_ID][str(i)] = True  # 标记为已下载
            self.save_log()

    def start_scraping(self):
        if not self.kyara_name:
            return
        
        os.makedirs(self.save_folder, exist_ok=True)
        if self.wav_flag.is_set():
            os.makedirs(self.save_wav_folder, exist_ok=True)
            self.log_queue.put(f"开始收集 {self.kyara_name[1]} .wav格式卡面故事语音数据...")
        else:
            os.makedirs(self.save_card_audio_folder, exist_ok=True)
            self.log_queue.put(f"开始收集 {self.kyara_name[1]} .mp3格式卡面故事语音数据...")

        driver = self.setup_browser()
        self.select_jp_server(driver)
        if self.stop_flag.is_set():
            driver.quit()
            exit()

        self.log_data = self.load_log()
        if not self.log_data:
            self.select_character(driver)
            card_IDs = self.extract_card_ids(driver)
            for card_ID in card_IDs:
                self.log_data.setdefault(card_ID, {"1": False, "2": False})
            self.save_log()
        else:
            card_IDs = [card_id for card_id, status in self.log_data.items() if not all(status.values())]

        if card_IDs:
            # 进度条
            completed = len([card_id for card_id, status in self.log_data.items() if all(status.values())])
            self.progress_queue.put(completed / len([card_id for card_id in self.log_data.items()]))

            for card_ID in card_IDs:
                # 调用单张爬取
                self.scrape_card_audio(driver, card_ID)
                # 更新进度条
                completed = len([card_id for card_id, status in self.log_data.items() if all(status.values())])
                self.progress_queue.put(completed / len([card_id for card_id in self.log_data.items()]))

            driver.quit()
            self.log_queue.put(f"已成功收集 {self.kyara_name[1]} 所有卡面故事语音")
        else:
            self.log_queue.put(f"未找到 {self.kyara_name[1]} 有关的卡面故事音频数据")
            driver.quit()
            exit()

def run_scraper(target_name, log_queue, progress_queue, stop_flag, wav_flag):
    scraper = BestdoriScraper(target_name, log_queue, progress_queue, stop_flag, wav_flag)
    scraper.start_scraping()
