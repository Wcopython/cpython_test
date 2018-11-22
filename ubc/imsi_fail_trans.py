# ! python
# -*- coding: utf-8 -*-

import sqlite3
import os

class CheckFailImsi(object):
    def __init__(self):
        self.db_path = '/tmp/db_cache/imsiSet.db'

    def check_db_exsists(self):
        if os.path.exists('/tmp/db_cache'):
            return True
        return False

    def query_imsi(self, imsi, white_table_tag=None):
        if not self.check_db_exsists():
            return None
        db_conn = sqlite3.connect(self.db_path)
        query_str = '''SELECT imsi FROM imsi_transfail WHERE imsi=%s ''' % str(imsi)
        if white_table_tag:
            query_str = '''SELECT imsi FROM imsi_white WHERE imsi=%s ''' % str(imsi)
        with db_conn:
            cur = db_conn.cursor()
            cur.execute(query_str)
            rs = cur.fetchall()
            if rs:
                return True
        return None

