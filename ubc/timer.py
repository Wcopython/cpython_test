import threading
class Timer(object):

    def __init__(self, time,fun_timer):
        self.fun_timer = fun_timer
        self.time = time


    def start(self):
        self.timer = threading.Timer(self.time, self.run)
        self.timer.setDaemon(True)
        self.timer.start()

    def run(self):
        if self.fun_timer:
            self.fun_timer()
        self.timer = threading.Timer(self.time, self.run)
        self.timer.setDaemon(True)
        self.timer.start()

