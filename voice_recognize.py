import sys
import os
import threading
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import pyaudio
import base64
import json
import requests
import numpy as np
from PIL import Image

# 百度API相关信息
API_KEY = 'cNugQWkN2IQJH5OAxt98kZYS'
SECRET_KEY = 'aA9WnsldiP1qyuVrXl9FKqaBJamiPQdI'
TOKEN_URL = 'https://aip.baidubce.com/oauth/2.0/token'
ASR_URL = 'https://vop.baidu.com/server_api'
THRESHOLDNUM = 30  # 静默时间，超过这个个数就保存文件
THRESHOLD = 100  # 设定停止采集阈值


class VoiceRecognizeWorker(QThread):
    recognized_text = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, token, parent=None):
        super().__init__(parent)
        self.token = token
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            audio_data = self.start_recording()
            if self.stop_event.is_set():
                break
            if audio_data:
                base64_audio = base64.b64encode(audio_data).decode('utf-8')
                params = {
                    'format': 'wav',
                    'rate': 16000,
                    'channel': 1,
                    'cuid': 'your_device_id',
                    'token': self.token,
                    'len': len(audio_data),
                    'speech': base64_audio
                }

                headers = {'Content-Type': 'application/json'}

                response = requests.post(ASR_URL, headers=headers, data=json.dumps(params))

                if response.status_code == 200:
                    result = response.json()
                    if result['err_no'] == 0:
                        text = result['result'][0] if result['result'][0] != '我不知道。' and result['result'][0] != '我不知道啊！' and result['result'][0] != '你不知道吗？' and result['result'][0] else "声音太小了，听不见喵~~"
                        self.recognized_text.emit(text)
                    else:
                        print("错误信息:", result['err_msg'])
                else:
                    print("请求失败:", response.status_code)

        self.finished.emit()

    def start_recording(self):
        p = pyaudio.PyAudio()
        count = 0
        frames = []
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
        while count < THRESHOLDNUM:
            if self.stop_event.is_set():
                break
            data = stream.read(1024, exception_on_overflow=False)
            np_data = np.frombuffer(data, dtype=np.int16)
            frame_energy = np.mean(np.abs(np_data))
            if frame_energy < THRESHOLD:
                count += 1
            elif count > 0:
                count -= 1
            frames.append(data)
        stream.stop_stream()
        stream.close()
        p.terminate()
        return b''.join(frames) if frames else None


class VoiceRecognizeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.worker_thread = None
        self.background_pixmap = None

    def initUI(self):
        self.setWindowTitle("洛琪希的声音魔术")
        self.setGeometry(300, 300, 500, 700)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        image_path = "1730247418524_compressed.png"
        self.background_pixmap = QPixmap(image_path)
        self.background_label = QLabel(self)
        self.background_label.setPixmap(self.background_pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.background_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.background_label)

        self.text_box = QTextEdit(self)
        self.text_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.text_box.setStyleSheet("background-color: white; color: black;")  # 设置背景颜色为白色，文字颜色为黑色
        layout.addWidget(self.text_box)

        button_container = QWidget(self)
        button_layout = QVBoxLayout(button_container)
        self.start_button = QPushButton("开始", self)
        self.start_button.clicked.connect(self.on_start)
        self.stop_button = QPushButton("结束", self)
        self.stop_button.clicked.connect(self.on_stop)
        self.stop_button.setEnabled(False)
        self.clear_button = QPushButton("清空", self)
        self.clear_button.clicked.connect(self.on_clear)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.clear_button)
        layout.addWidget(button_container)

        # 设置按钮样式
        self.setStyleSheet("""
            QLabel { background-color: transparent; }
            QWidget { background-color: transparent; }
            QPushButton {
                background-color: #4CAF50; /* 绿色背景 */
                border: 2px solid #000; /* 黑色边框 */
                color: white; /* 白色文字 */
                padding: 10px 20px;
                font-size: 16px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #45a049; /* 悬停时的背景颜色 */
            }
            QPushButton:pressed {
                background-color: #3e8e41; /* 按下时的背景颜色 */
            }
            QPushButton:disabled {
                background-color: #cccccc; /* 禁用时的背景颜色 */
                color: #666666; /* 禁用时的文字颜色 */
            }
        """)

    def on_start(self):
        global access_token
        if self.worker_thread is not None and self.worker_thread.isRunning():
            return

        self.worker_thread = VoiceRecognizeWorker(access_token)
        self.worker_thread.recognized_text.connect(self.update_text_box)
        self.worker_thread.finished.connect(self.on_worker_finished)
        self.worker_thread.start()
        self.stop_button.setEnabled(True)
        self.start_button.setEnabled(False)

    def on_stop(self):
        if self.worker_thread is not None and self.worker_thread.isRunning():
            self.worker_thread.stop_event.set()

    def on_worker_finished(self):
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(True)

    def update_text_box(self, text):
        self.text_box.append(text)

    def on_clear(self):
        self.text_box.clear()


def get_access_token(api_key, secret_key):
    """ 获取access token """
    params = {
        'grant_type': 'client_credentials',
        'client_id': api_key,
        'client_secret': secret_key
    }
    response = requests.post(TOKEN_URL, data=params)
    if response.status_code == 200:
        result = response.json()
        return result.get('access_token')
    else:
        raise Exception("Failed to get access token")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VoiceRecognizeApp()
    icon = QIcon("icon.png")
    window.setWindowIcon(icon)
    window.show()

    # 获取access token
    access_token = get_access_token(API_KEY, SECRET_KEY)

    sys.exit(app.exec_())