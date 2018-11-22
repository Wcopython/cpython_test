# -*- conding:utf-8 -*-
import time
from datetime import datetime
from datetime import timedelta

DELTA_HOURS = 8
class TimeDelta(object):

    @classmethod
    def time(self):
        """ time_now delta 8 hours
        """
        time_now = time.time() + DELTA_HOURS*60*60
        return time_now
    
    @classmethod
    def sleep(self, arg_time):
        return time.sleep(arg_time)

class DatetimeDelta(object):
    #def __init__(self):
        #super(DatetimeDelta,self).__init__()
    @classmethod
    def now(self):
        cur_time = datetime.now()
        deltaed_time = cur_time + timedelta(hours=DELTA_HOURS)
        return deltaed_time
    
    @classmethod
    def asctime(self):
        return self.now().strftime('%Y-%m-%d %H:%M:%S')


if __name__ =='__main__':
   pass