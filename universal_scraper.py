import os
import re
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from concurrent.futures import ThreadPoolExecutor, as_completed
from get_path import resource_path

'''
不做筛选对所有数据进行遍历后分类储存
start为起始ID end为终止ID
restart_interval为浏览器重启间隔ID数
save_interval为保存间隔
max_workers为同时下载数

截至20250412
afterlive: 1-1864  √
area: 1-650 10001-11109 20001-20095 30000-30151 50001-50500 60001-60378 61053-61210 80001-80125 88601-88607 99901-99905  √
band: 1-493  √
card: 1-2193   中文语料截止 2062  √
event: 1-291   中文语料截止 271  √
main: 1-73  √

'''
VALID_SERVERS = ["cn", "jp"]  # 如果要加入 en 需要在角色名映射文件中添加英文服务器中的角色名 如yukina  另外：这行代码没用到 纯醒目标识
VALID_KEY_WORD = ["afterlive", "area", "band", "card", "event", "main"]   # 这行代码没用 醒目标识

class BestdoriScraper:
    def __init__(self, key_word = "afterlive", server = "jp", start=1, end=8, restart_interval=500, save_interval=8, max_workers=8):
        self.key_word = key_word
        self.server = server
        self.start_ID = start
        self.end_ID = end + 1
        self.card_IDs = range(self.start_ID, self.end_ID)           # 当前卡面id范围
        self.restart_interval = restart_interval
        self.save_interval = save_interval
        self.max_workers = max_workers                  # 并发线程数
        self.kyara_map = self._get_character_map()
        self.kyara_list = self.kyara_map.keys()
        self.start_url = "https://bestdori.com/info/cards"  # 随便填，能让网站混个面熟就行...
        self.save_folder = os.path.join(os.getcwd(), "data", self.key_word)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UserAgent().random})
        self.download_tasks = []                        # 存放所有 (url, path) 对
        self.restart_by_ckp_flag = True               # True 从上次保存的地方下载
        self.sleep_time = 1  


        if self.server == "jp":
            self.ui_lan = "日"
        elif self.server == "cn":
            self.ui_lan = "简"
        else:
            raise ValueError(f"无效或者暂不支持的服务器类型: {self.server}")
        
        if self.key_word == "event":
            self.sub_list = range(1, 11)
        elif self.key_word == "main":
            self.sub_list = [None]
        elif self.key_word == "band":
            self.sub_list = [None]
        elif self.key_word == "card":
            self.sub_list = [2,1]
        elif self.key_word == "area":
            self.sub_list = [None]
        elif self.key_word == "afterlive":
            self.sub_list = [None]
        else:
            raise ValueError(f"无效或者暂不支持的任务类型: {self.key_word}")

    def _get_character_map(self):
        try:
            with open(resource_path("characters.json"), "r", encoding="utf-8") as f:
                character_map = json.load(f)
            return character_map
        except FileNotFoundError:
            print("错误: 未找到角色映射文件 characters.json")
            return None

    def _setup_browser(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(self.start_url)
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(self.sleep_time)
        return driver
    
    # 选择日服服务器
    def _select_jp_server(self, driver):
        try:
            UI_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, f"//a[contains(@class, 'button is-rounded round') and .//span[@class='icon' and text()='{self.ui_lan}']]")))
            if "is-focused" not in UI_button.get_attribute("class"):
                UI_button.click()
            server_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'button is-rounded round') and .//img[contains(@alt, 'JP')]]")))  # JP没错，不能动
            if "is-focused" not in server_button.get_attribute("class"):
                server_button.click()
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'button') and .//i[contains(@class, 'fas fa-times')]]"))).click()
            time.sleep(self.sleep_time)
        except Exception as e:
            print(f"服务器选择失败: {e}")
            return
           
    # 处理文本(audio name)
    def _clean_dialogue(self, dialogue):
        dialogue = dialogue.replace("（", "")
        dialogue = dialogue.replace("）", "")
        temp_pattern = r"([、と])?(新人スタッフさん|新人スタッフさーん(?:も|は|が|に|を|の|と)?)([。、？！]?)"
        dialogue = re.sub(temp_pattern, lambda match: "…" if match.group(1) else "", dialogue)
        return dialogue
    
    # 处理文本(dialogue)
    def _clean_dialogue_text(self, dialogue):
        dialogue = re.sub(r"\s+", "", dialogue)
        dialogue = re.sub(r"[\u3000]+", "", dialogue)
        return dialogue
    
    # 下载音频
    def _download_audio(self, audio_url, save_path):
        try:
            response = self.session.get(audio_url, stream=True, timeout=10)
            response.raise_for_status()
            with open(save_path, "wb") as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
        except Exception as e:
            return audio_url, False, str(e)
        return audio_url, True, None

    def _scrape_card_audio(self, driver, card_ID):
        
        names = []
        dialogues = []

        for i in self.sub_list:
            if i:
                driver.get(f"https://bestdori.com/tool/storyviewer/{self.key_word}/{self.server}/{card_ID}/{i}")
            else:
                driver.get(f"https://bestdori.com/tool/storyviewer/{self.key_word}/{self.server}/{card_ID}")
            WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            time.sleep(self.sleep_time)
            try:
                list_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'button is-rounded round') and .//i[contains(@class, 'fa-bars')]]")))
                if "is-focused" not in list_button.get_attribute("class"):
                    list_button.click()
            except:
                if names:
                    card_dialogue = dict(zip(names, dialogues))
                    print(f"ID {card_ID} : done")
                    return card_dialogue
                else:
                    print(f"{self.key_word} ID {card_ID} : 没有对应故事")
                    return
            time.sleep(self.sleep_time)

            page_source = driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")
            dialogue_blocks = soup.find_all("a", class_="box bg-white download-container")

            jun = 1

            for block in dialogue_blocks:
                # 文字部分
                name_tag = block.find("div", class_="m-b-xs fg-text")
                name = name_tag.find_all("span")[-1].text.strip() if name_tag else "???"
                
                dialogue_tags = block.find_all("div", class_="column")
                dialogue = next((tag.text.strip() for tag in dialogue_tags if tag.text.strip()), "")
                dialogue = self._clean_dialogue_text(dialogue)
                if name and dialogue:
                    key = f"{self.key_word}_{card_ID}_{i}_{jun}_{self.server}"      # 生成唯一键
                    if name in self.kyara_list:
                        key = f"{self.kyara_map[name][2]}_{key}"
                    elif name in {"まりな", "凛々子", "麻里奈", "凛凛子"}:
                        key = f"staff_{key}"
                    else:
                        key = f"others_{key}"
                    
                    # 存储当前i的数据
                    names.append(key)
                    dialogues.append(dialogue)
                    jun += 1

                # 中文剧情就不往下执行了 懒得解耦
                if self.server == "cn":
                    continue
                
                # 音频部分
                dialogue_audio_name = self._clean_dialogue(dialogue)

                audio_tag = block.find("a", class_="button is-small", href=True)
                if audio_tag:
                    audio_url = "https://bestdori.com" + audio_tag["href"]
                else:
                    audio_url = None

                if audio_url:
                    file_name = re.sub(r'[\/:*?"<>|]', '', dialogue_audio_name)
                    if name in self.kyara_list:
                        dir_name = self.kyara_map[name][3]
                        sub_dir = self.kyara_map[name][2]
                        daddy_path = os.path.join(self.save_folder, dir_name, sub_dir)
                    elif name in {"まりな", "凛々子"}:
                        daddy_path = os.path.join(self.save_folder, name)
                    else:
                        daddy_path = os.path.join(self.save_folder, "others")

                    os.makedirs(daddy_path, exist_ok=True)

                    file_name_part = f"{name}_{file_name}" if name not in self.kyara_list and name not in {"まりな", "凛々子"} else file_name
                    file_path = os.path.join(daddy_path, f"{file_name_part}.mp3")

                    if not os.path.exists(file_path):
                        self.download_tasks.append((audio_url, file_path))
            
        card_dialogue = dict(zip(names, dialogues))
        print(f"ID {card_ID} : done")
        return card_dialogue
    
    def _save_json(self, data, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    # 并行下载所有积累的音频任务
    def _download_all(self):
        if not self.download_tasks:
            return
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._download_audio, url, path): (url, path)
                       for url, path in self.download_tasks}
            total = len(futures)
            for count, fut in enumerate(as_completed(futures), start=1):
                url, path = futures[fut]
                if count % 100 == 0 or count == total:
                    print(f"进度: {count}/{total}")
                try:
                    _, success, err = fut.result()
                    if not success:
                        print(f"[下载失败] {url} -> {path} 错误: {err}")
                except Exception as e:
                    print(f"[下载异常] {url} -> {path} 异常: {e}")
        # 清空任务列表
        self.download_tasks.clear()

    def start_scraping(self):

        os.makedirs(self.save_folder, exist_ok=True)
                
        file_path = os.path.join(self.save_folder, f"{self.key_word}_dialogue_{self.server}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    card_dialogue_all = json.load(f)
                if card_dialogue_all and self.restart_by_ckp_flag:
                    try:   # 从上次结束的点开始
                        last_key = list(card_dialogue_all.keys())[-1]
                        self.start_ID = int(last_key.split("_")[2]) + 1 # 中断时, 对话会收录完最后一个ID所有对话再退出
                    except:
                        pass
                    self.card_IDs = range(self.start_ID, self.end_ID)
            except Exception as e:
                card_dialogue_all = {}
        else:
            card_dialogue_all = {}

        driver = None

        try:
            driver = self._setup_browser()
            self._select_jp_server(driver)
            for idx, card_ID in enumerate(self.card_IDs, start=1):

                try:        # 调用单张爬虫
                    card_dialogue = self._scrape_card_audio(driver, card_ID)
                except Exception as e:
                    print(f"[{self.key_word} ID {card_ID} 抓取失败] {e}")
                    continue
                if card_dialogue:
                    card_dialogue_all.update(card_dialogue)

                # 保存点: 保存对话，下载资源
                if idx % self.save_interval == 0:
                    print(f"已处理 {idx} 个ID, 正在保存和下载资源...")
                    self._save_json(card_dialogue_all, file_path)
                    self._download_all()   

                # 每隔一段时间重启浏览器
                if idx % self.restart_interval == 0:
                    print(f"重启浏览器中...")
                    driver.quit()
                    driver = self._setup_browser()
                    self._select_jp_server(driver)
                
        except KeyboardInterrupt:
            print("\n正在保存数据, 请不要关闭...")

        finally:
            # 异常退出终止保存数据
            self._save_json(card_dialogue_all, file_path)
            self._download_all()
            print("\n保存完成!")
            if driver:
                driver.quit()

if __name__ == "__main__":
    try:
        scraper = BestdoriScraper()
        scraper.start_scraping()
    except Exception as e:
        print(f"Error: {e}")
