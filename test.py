import logging


class readLog():
    start_point = 0
    def __init__(self):
        super().__init__()
        with open('app.log', 'rb') as file:
            file.seek(0,2)
            self.start_point = file.tell()

    def log_connect(self):
        with open('app.log','rb') as file:
            file.seek(self.start_point,1)
            log_connect = file.read()
            self.start_point = file.tell()
            print(log_connect)

if __name__ == '__main__':
    readlog = readLog()
    print(readlog.start_point)
    logging.basicConfig(filename='app.log', level=logging.INFO)
    logging.info('hello')
    readlog.log_connect()