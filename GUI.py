from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout, QPlainTextEdit, QWidget
from PyQt5.QtCore import QThread, pyqtSignal
import sys
import random
from datetime import datetime
import requests
import re
from bs4 import BeautifulSoup
import json
import time
import configparser

class CheckInThread(QThread):
    check_in_signal = pyqtSignal(str)

    def __init__(self, account, password, lng, lat):
        super().__init__()
        self.account = account
        self.password = password
        self.lng = lng
        self.lat = lat
        self.session = requests.Session()
        self.config = configparser.ConfigParser()
        self.isLoop = True

    def run(self):
        login = "https://irs.zuvio.com.tw/irs/submitLogin"

        data = {
            'email': self.account + "@nkust.edu.tw",
            'password': self.password,
            'current_language': "zh-TW"
        }
        response = self.session.post(login, data=data)
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            scripts = soup.find_all("script", string=re.compile('var accessToken = "(.*?)";'))
            user_id = str(scripts[0]).split('var user_id = ')[1].split(";")[0]
            accessToken = str(scripts[0]).split('var accessToken = "')[1].split("\";")[0]
        except:
            self.check_in_signal.emit("登入失敗！")
            return

        url = f"https://irs.zuvio.com.tw/course/listStudentCurrentCourses?user_id={user_id}&accessToken={accessToken}"
        response = self.session.get(url)
        course_json = json.loads(response.content)
        
        if course_json['status']:
            self.check_in_signal.emit(f"今天是 {datetime.today().strftime('%Y/%m/%d')}")
            self.check_in_signal.emit("這學期有修的課為：")
            for course_data in course_json['courses']:
                if "Zuvio" not in course_data['teacher_name']:
                    self.check_in_signal.emit(course_data['course_name'] + " - " + course_data['teacher_name'])
            already_checked = []
            while self.isLoop:
                has_course_available = False
                for course_data in course_json['courses']:
                    if course_data in already_checked:
                        continue
                    if "Zuvio" not in course_data['teacher_name']:
                        rollcall_id = self.check(course_data['course_id'])
                        if rollcall_id != "":
                            result = course_data['course_name'] + self.checkIn(user_id, accessToken, rollcall_id)
                            self.check_in_signal.emit(result)
                            has_course_available = True
                already_checked.append(course_data)
                time.sleep(random.randint(1, 5))
                if not has_course_available:
                    result = f"{datetime.today().strftime('%H:%M:%S')} 尚未有課程開放簽到"
                    self.check_in_signal.emit(result)

    def check(self, course_ID):
        url = f"https://irs.zuvio.com.tw/student5/irs/rollcall/{course_ID}"
        response = self.session.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        scripts = soup.find_all("script", string=re.compile("var rollcall_id = '(.*?)';"))
        rollcall_id = str(scripts[0]).split("var rollcall_id = '")[1].split("';")[0]
        return rollcall_id

    def checkIn(self, user_id, accessToken, rollcall_id):
        url = "https://irs.zuvio.com.tw/app_v2/makeRollcall"
        lat = self.lat
        lng = self.lng
        data = {
            'user_id': user_id,
            'accessToken': accessToken,
            'rollcall_id': rollcall_id,
            'device': 'WEB',
            'lat': lat,
            'lng': lng
        }
        response = self.session.post(url, data=data)
        jsonres = json.loads(response.text)
        if jsonres['status']:
            return " - 簽到成功！"
        else:
            return " - 簽到失敗：" + jsonres['msg']

class MyWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        self.account_label = QLabel("學號：")
        self.account_input = QLineEdit(self)

        self.password_label = QLabel("密碼：")
        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)

        self.lng_label = QLabel("經度：")
        self.lng_input = QLineEdit(self)

        self.lat_label = QLabel("緯度：")
        self.lat_input = QLineEdit(self)

        self.start_button = QPushButton("開始簽到", self)
        self.start_button.clicked.connect(self.start_check_in)

        self.result_text = QPlainTextEdit(self)
        self.result_text.setReadOnly(True)

        self.layout.addWidget(self.account_label)
        self.layout.addWidget(self.account_input)
        self.layout.addWidget(self.password_label)
        self.layout.addWidget(self.password_input)
        self.layout.addWidget(self.lng_label)
        self.layout.addWidget(self.lng_input)
        self.layout.addWidget(self.lat_label)
        self.layout.addWidget(self.lat_input)
        self.layout.addWidget(self.start_button)
        self.layout.addWidget(self.result_text)

        self.check_in_thread = None

    def start_check_in(self):
        account = self.account_input.text()
        password = self.password_input.text()
        lng = self.lng_input.text()
        lat = self.lat_input.text()

        if not account or not password or not lng or not lat:
            self.result_text.setPlainText("請輸入學號、密碼、經度和緯度")
            return

        if not self.check_in_thread or not self.check_in_thread.isRunning():
            self.check_in_thread = CheckInThread(account, password, lng, lat)
            self.check_in_thread.check_in_signal.connect(self.show_message)
            self.check_in_thread.start()
        else:
            self.result_text.setPlainText("簽到執行中，請稍候")

    def show_message(self, message):
        current_text = self.result_text.toPlainText()
        self.result_text.setPlainText(current_text + "\n" + message)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec_())
