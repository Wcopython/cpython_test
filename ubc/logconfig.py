import logging
import logging.config
import os

from time_delta import DatetimeDelta

class TimezoneFormatter(logging.Formatter):
    def __init__(self, fmt, datefmt,timezone=None):
        #self.timezone = timezone or pytz.timezone('Asia/ShangHai')
        super(TimezoneFormatter, self).__init__(fmt, datefmt)

    def formatTime(self, record, datefmt=None):
        if datefmt:
            dt = DatetimeDelta.now()
            return dt.strftime(datefmt)
        else:
            return super(TimezoneFormatter, self).formatTime(record, datefmt)

file_path = os.path.dirname(os.path.abspath(__file__))
ubcconfig_file = os.path.join(file_path,'logger.conf')
logging.config.fileConfig(ubcconfig_file)
logger = logging.getLogger('guest')
for handler in logger.handlers:
        handler.setFormatter(TimezoneFormatter(handler.formatter._fmt, handler.formatter.datefmt,))