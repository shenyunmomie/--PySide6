import shutil
import time

from PySide6.QtWidgets import *
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QIcon
from PySide6.QtCore import *

from queue import Queue
import sys,os
import wave
import numpy as np
import logging

support_audio = ['pcm','wav']
log_format = "%(asctime)s - %(levelname)s - %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(filename='app.log',level=logging.INFO,format=log_format,datefmt=date_format)


class readLog():
    start_point = 0
    def __init__(self):
        super().__init__()
        with open('app.log', 'rb') as file:
            file.seek(0, 2)
            self.start_point = file.tell()

    def main(self):
        with open('app.log','rb') as file:
            file.seek(self.start_point,1)
            log_connect = file.read()
            self.start_point = file.tell()
        return log_connect

#---------搜索音频文件,创建对应保存路径-----------
def search_files(root_path,save_path,all_files = []):
    filename_list = os.listdir(root_path)   # 搜索子文件的文件名
    for filename in filename_list:
        cur_path = os.path.join(root_path,filename) # 子文件的绝对地址
        crt_path = cur_path.replace(root_path, save_path)   #保存路径下的地址
        if os.path.isdir(cur_path):     # 判断子文件是否为目录
            # 如果为目录，创建该目录
            if not os.path.exists(crt_path):
                os.makedirs(crt_path)
            # 递归，继续查询该子目录下的其他子目录
            search_files(cur_path,save_path,all_files)
        elif cur_path[-3:] in support_audio:   # 如果是音频文件则添加,建议加入检测音频文件是否合法的方法
            all_files.append(cur_path)
        else:   #其他文件则原样复制到保存路径
            shutil.copy(cur_path,crt_path)
    return all_files

# 转换格式的线程
class tsfTread(QThread):
    pgbar_sign = Signal(int, int)
    tsf_end_sign = Signal()

    def __init__(self):
        super().__init__()

    def set_param(self,all_files,root_path, save_path, type):
        self.all_files = all_files
        self.root_path = root_path
        self.save_path = save_path
        self.type = type

    # pcm转wav格式，单声道，采样精度，采样率
    def pcm2wav(self,file_path,copy_path, channels=1, bits=16, sample_rate=16000):
        with open(file_path, 'rb') as f:
            pcmdata = f.read()

        if bits % 8 != 0:
            raise ValueError("bits % 8 must == 0. now bits:" + str(bits))

        wavfile = wave.open(copy_path, 'wb')
        wavfile.setnchannels(channels)
        wavfile.setsampwidth(bits // 8)
        wavfile.setframerate(sample_rate)
        wavfile.writeframes(pcmdata)
        wavfile.close()
        return

    # wav转pcm格式
    def wav2pcm(self,file_path,copy_path, data_type=np.int16):
        with open(file_path, 'rb') as f:
            f.seek(0)
            f.read(44)
            data = np.fromfile(f, dtype=data_type)
            data.tofile(copy_path)
        return

    def run(self):
        total = len(self.all_files)
        count = 0
        for file_path in self.all_files:
            count += 1
            logging.info(f'正在转换{file_path}')
            time.sleep(1)
            if self.type == 'p2w':
                copy_path = file_path.replace(self.root_path, self.save_path)[:-4] + '.wav'
                self.pcm2wav(file_path,copy_path)
            elif self.type == 'w2p':
                copy_path = file_path.replace(self.root_path, self.save_path)[:-4] + '.pcm'
                self.wav2pcm(file_path,copy_path)
            logging.info('转换完成')
            self.pgbar_sign.emit(count, total)
        self.tsf_end_sign.emit()
        return

# 自定义信号源对象类型，一定要继承自QObject
class MySignals(QObject):
    # 调用 emit方法 发信号时，传入参数，必须是这里指定的 参数类型
    path_checked = Signal(str)
    file_searched = Signal(str,list)


class Stats(QWidget):

    def __init__(self):
        super().__init__()
        # 从文件中加载UI定义
        # 从 UI 定义中动态 创建一个相应的窗口对象
        # 注意：里面的控件对象也成为窗口对象的属性了
        # 比如 self.ui.button , self.ui.textEdit
        self.ui = QUiLoader().load('格式转换ui.ui')
        self.ui.pgbar.setRange(0,100)
        self.ui.pgbar.setValue(0)

        self.ms = MySignals()   #自定义信号类
        self.tsft = tsfTread()  #格式转换类
        self.logthread = readLog()  #读取日志
        self.timer = QTimer()   #计时器，每隔500ms读一次日志

        self.ui.tsfBtn.clicked.connect(self.showInvalidPathDialog)  #转换按钮按下后，先检查路径、选项是否合法
        self.ui.file_pbtn.clicked.connect(self.selectFilePath)  #可以通过文件选择框输入文件路径
        self.ui.file_pbtn_2.clicked.connect(self.selectFilePath)#可以通过文件选择框输入文件路径

        self.ms.path_checked.connect(self.file_search)  #检查完合法后，搜索路径下的所有音频文件，并将源文件结构复制到保存路径下
        self.ms.file_searched.connect(self.tsfFun)  #搜索完文件后，调用格式转换线程

        self.tsft.pgbar_sign.connect(self.refreshBar)   #进度条更新
        self.tsft.tsf_end_sign.connect(self.success_tsf)    #转换完毕弹出成功窗口

        self.timer.timeout.connect(self.outputControl)  #计时器，每500ms读取日志并打印控制台

        self.timer.start(500)   #计时器启动

        logging.info('===app启动===')

    # 检查路径是否合法
    def showInvalidPathDialog(self):

        self.root_path = self.ui.rootPath.text()
        self.save_path = self.ui.savePath.text()
        logging.info(f'文件路径:{self.root_path}\n保存路径：{self.save_path}\n====正在检查路径是否合法====')
        if os.path.isabs(self.root_path) and os.path.isabs(self.save_path):
            if os.path.exists(self.root_path):  #and os.path.exists(self.save_path)
                if self.ui.p2w_rbtn.isChecked():
                    self.ms.path_checked.emit('p2w')
                elif self.ui.w2p_rbtn.isChecked():
                    self.ms.path_checked.emit('w2p')
                else:
                    QMessageBox.information(self.ui,'未选中','未选择需要转换类型',QMessageBox.Close)
                    return
            else:
                QMessageBox.information(self.ui,'路径问题','路径不存在，请选择正确的路径',QMessageBox.Close)
                return
        else:
            QMessageBox.information(self.ui,'路径问题','请输入绝对路径',QMessageBox.Close)
            return

    # 调用search_files函数，建议创建一个线程
    def file_search(self,type):
        logging.info('====正在搜索路径内的所有音频文件====')
        all_files = search_files(self.root_path,self.save_path)
        self.ms.file_searched.emit(type,all_files)
        return

    # 选择路径
    def selectFilePath(self):
        dir = QFileDialog(self.ui,'选择文件夹')
        dir.setAcceptMode(QFileDialog.AcceptOpen)
        dir.setFileMode(QFileDialog.Directory)
        dir.setDirectory(sys.argv[0])
        path = dir.getExistingDirectory()

        sender = self.sender()
        print(sender.objectName())
        if sender.objectName() == 'file_pbtn':
            self.ui.rootPath.setText(path)
        elif sender.objectName() == 'file_pbtn_2':
            self.ui.savePath.setText(path)

    # 运行格式转换线程
    def tsfFun(self, type, all_files):
        logging.info('====格式转换开始====')

        self.tsft.set_param(all_files,self.root_path, self.save_path, type)
        self.tsft.start()

        return

    # 完成时的弹窗
    def success_tsf(self):
        logging.info('已完成\n')
        # self.logthread.quit()
        QMessageBox.information(self.ui, "完成", "已经完成格式转换", QMessageBox.Close)

    # 读取日志文件并写入控制台
    def outputControl(self):
        log_connect = self.logthread.main().decode("utf-8",errors="ignore")
        if log_connect != '':
            self.ui.outputControl.append(log_connect)

    # 进度条更新
    def refreshBar(self,num,total):
        self.ui.pgbar.setValue((num/total)*100)


if __name__ == '__main__':
    app = QApplication([])

    # E:\pythoncode\测试工具\test\pcmCase
    # C:\Users\神殒魔灭\Desktop\p2wTest

    # C:\Users\神殒魔灭\Desktop\w2pTest

    app.setWindowIcon(QIcon('png/logo.png'))

    test = Stats()
    test.ui.show()

    sys.exit(app.exec())