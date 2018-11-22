#coding=utf-8
import  socket
import json
import os
import threading
try:
    if not os.path.exists('/tmp/ubc/log'):
        os.makedirs('/tmp/log/ubc')
    if not os.path.exists('tmp/syncimsinum'):
        os.makedirs('tmp/rptimsinum')
except Exception,e:
    pass
base_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(base_path)
from tool import Tool
from database import MyDataBase
from logconfig import logger
from timer import Timer
from imsi_fail_trans import CheckFailImsi
from appconfig import IMSI_NUM_FOR_TAG_UPDATE
from appconfig import WORKING_MODE

path_sync_imsinum = '/tmp/syncimsinum/'
mobile_table_name = 'mobilecom'
union_table_name = 'unicom'
tele_table_name = 'telecom'
OTHER = 'other'
VERSION = '1.4'

class MsgKey():
    id = 'id'
    ubc = 'ubc'
    imsi = 'imsi'
    info = 'info'
    type = 'type'
    module = 'module'
    ubc_info = 'ubc_info'
    imsi_list = 'imsilist'
    g_2_4_tag = 'g_2_4_tag'

#receive message id
class RcvMsgId_value():

    ubc_chg_tac = 'MSG_CHG_TAC'
    ntc_heartbeat = 'NTC_HEARTBEAT'
    ubc_get_imsi = 'MSG_UBC_GET_IMSI'
    ntc_query_imsi = 'NTC_QUERY_IMSI'
    ntc_insert_imsi = 'NTC_INSERT_IMSI'
    ntc_sync_imsi = 'START_SYNC_IMSINUM'
    ubc_heartbeat = 'MSG_UBC_HEARTBEAT'
#response message id
class RspMsgId_value():

    ntc_set_imsi = 'NTC_SET_IMSI'
    ubc_set_imsi = 'MSG_SET_IMSI_UBC'
    ubc_heartbeat_ack = 'MSG_UBC_HEARTBEAT_ACK'
    ntc_insert_imsi_ack = 'NTC_INSERT_IMSI_ACK'
    ntc_query_imsi_ack = 'NTC_QUERY_IMSI_ACK'
    ntc_query_imsi_rep = 'NTC_QUERY_IMSI_REP'
    ubc_get_imsi_num = 'UBC_GET_IMSI_NUM'

db_info = {
    'mcc_of_china':'460',
    '00': mobile_table_name,
    '02': mobile_table_name,
    '04': mobile_table_name,
    '07': mobile_table_name,
    '01': union_table_name,
    '06': union_table_name,
    '09': union_table_name,
    '03': tele_table_name,
    '05': tele_table_name,
    '11': tele_table_name,
    '20': tele_table_name,
    'other': OTHER
}
arfcn = {mobile_table_name: 89, union_table_name: 120, tele_table_name: 0}
class Ubc(object):
    BUF_SIZE = 1024
    MESSAGE_HEADER_LENGTH = 8
    REJECT = 1
    REDIRECT = 2
    REJECT_ONCE = 3
    report_imsi_num_4G = 0
    report_imsi_num_4G_tmp = 0
    report_mobile_imsi_num_4G = 0
    report_mobile_imsi_num_4G_tmp = 0
    report_union_imsi_num_4G = 0
    report_union_imsi_num_4G_tmp = 0
    imsi_num_for_tag_update = IMSI_NUM_FOR_TAG_UPDATE

    dispatch = {}

    def __init__(self, ip, port):
        Ubc._create_socket(ip, port)
        self._init_database()
        self.mobile_4G_empty_ue_num = 0
        self.union_4G_empty_ue_num = 0
        self.address_2GC = None
        self.catpool_num = 1
        self.sync_imsinum_tag = threading.Event()
        self.sync_imsinum_tag.clear()
        self.mobile_2G_empty_ue_num = 0
        self.union_2G_empty_ue_num = 0
        self.work_mode = WORKING_MODE
        #self.imsi_num_for_tag_update = IMSI_NUM_FOR_TAG_UPDATE
        self.check_fail_imsi_db = CheckFailImsi()

        self.sync_imsinum_thread = threading.Thread(target = self.sync_imsinum)
        self.sync_imsinum_thread.setDaemon(True)
        self.sync_imsinum_thread.start()

    #  同步imsinum 数据
    def sync_imsinum(self):
        while True:
            if self.sync_imsinum_tag.is_set():
                logger.info('start to sync imsinum')
                for file_name in os.listdir(path_sync_imsinum):
                    sync_file = path_sync_imsinum + file_name
                    logger.debug('sync sync_file is %s' % sync_file)
                    if sync_file.endswith('.txt'):
                        gener = self.read_sync_imsi_file(sync_file)
                        if gener:
                            self.save_sync_imsinum(gener)
                        try:
                            os.remove(sync_file)
                        except Exception as e:
                            logger.error('remove sync file error: %s' % str(e))
                    else:
                        try:
                            os.remove(sync_file)
                        except Exception as e:
                            logger.error('remove other files error: %s' % str(e))
                self.sync_imsinum_tag.clear()
                logger.info('sync success')
            else:
                logger.info('wait to sync imsinum')
                self.sync_imsinum_tag.wait()

    # 读取同步文件, 返回imsi生成器
    def read_sync_imsi_file(self, file_path):
        try:
            imsinum_gener = (imsi for imsi in open(file_path))
            return imsinum_gener
        except Exception as e:
            logger.error('generate generator error :%s' % str(e))
        #with open(file_path) as op:
            #imsinum_gener = (imsi for imsi in op.readlines())
        return None

    def save_sync_imsinum(self, gener):
        for imsi_info in gener:
            imsi = imsi_info.strip('\n\t')
            message = {'imsilist': []}
            message['imsilist'].append(imsi)
            logger.debug('sync_message is: %s' % str(message))
            self._process_ntc_insert_imsi(message, None)
            #self._process_ntc_sync_imsi(message)
    #定时器函数，循环触发判断4G上报的IMSI数量是否过少了，是的话则给4G发送TAC指令重入

    @classmethod
    def func_timer(cls):
        #cls._response(('', 6070), id=RcvMsgId_value.ubc_chg_tac)
        #logger.debug('&&&&& ***** report_imsi_num_4G func_timer:{}  report_imsi_num_4G_tmp:{} '.format(cls.report_imsi_num_4G, cls.report_imsi_num_4G_tmp))
        #cls._response(('',6070), id=RcvMsgId_value.ubc_chg_tac)
        if cls.report_imsi_num_4G_tmp is 0:#同步一下
            cls.report_imsi_num_4G_tmp = cls.report_imsi_num_4G
        else:
            if (cls.report_imsi_num_4G_tmp + cls.imsi_num_for_tag_update) >  cls.report_imsi_num_4G:
                # send tac update apply
                logger.debug('ubc_chg_tag_ :%s' % str(RcvMsgId_value.ubc_chg_tac))
                cls._response(('', 6070), id=RcvMsgId_value.ubc_chg_tac)

            # calculate mobile , union imsi nums in a minute
            #mobile_get_num = cls.report_mobile_imsi_num_4G - cls.report_mobile_imsi_num_4G_tmp
            #union_get_num = cls.report_union_imsi_num_4G - cls.report_union_imsi_num_4G_tmp

            # send mobile,union num to NTC module
            #if self.address_2GC:
            #cls._response(cls.address_2GC, id=RspMsgId_value.ubc_get_imsi_num,
                          #mbnum=str(mobile_get_num), unnum=str(union_get_num))

            cls.report_imsi_num_4G_tmp = cls.report_imsi_num_4G
            #cls.report_mobile_imsi_num_4g_tmp = cls.report_union_imsi_num_4G
            #cls.report_union_imsi_num_4G_tmp = cls.report_union_imsi_num_4G

    #初始化数据库，建立4张表。移动，联通，電信,OTHER
    def _init_database(self):
        """Connect to database and create all table."""
        self.database = MyDataBase()
        self.database.create_table(mobile_table_name)
        self.database.create_table(union_table_name)
        self.database.create_table(tele_table_name)
        self.database.create_table(OTHER)

    #建立本地的UDP
    @classmethod
    def _create_socket(cls, ip, port):
        """Create socket based on ip and port.Family is AF_INET and type is SOCK_DGRAM.
        ip:type:string
        port:type:int
        """
        address = (ip, port)
        cls.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cls.sock.bind(address)

    #处理ntc模块上报的心跳包
    def _process_ntc_heartbeat(self, message, address):
        """process the heartbeat message from client.get the number of 4G Mobile translation modules \
        and the number of 4G Union translation modules.
        message:type:dict
        """
        arfcn[mobile_table_name], b2GUENum1, self.mobile_4G_empty_ue_num , b2GIMSINum1, b4GIMSINum1, \
        arfcn[union_table_name], b2GUENum2, self.union_4G_empty_ue_num, b2GIMSINum2, b4GIMSINum2 = message.get(MsgKey.info)
        self.address_2GC = address
        self.catpool_num = int(message.get('catpool_count'))
        self.mobile_2G_empty_ue_num = b2GUENum1
        self.union_2G_empty_ue_num = b2GUENum2

    dispatch[RcvMsgId_value.ntc_heartbeat] = _process_ntc_heartbeat

    #处理ntc模块上报的查询数据库的消息
    def _process_ntc_query_imsi(self, message, address):
        """process the heartbeat message from client.get the number of 4G Mobile translation modules \
        and the number of 4G Union translation modules.
        message:type:dict
        address:type:tuple
        """
        response_imsi_list = []
        true_response_imsi_list = []
        logger.debug("rcvd msg:{} from {}".format(message, address))
        recv_imsi_list = message.get(MsgKey.imsi_list)#the type of recv_imsi_list list
        #get imsi from imsi_list
        if  recv_imsi_list is None:
            logger.error("**recv_imsi_list is None.")
            return
        try:
            for imsi in recv_imsi_list:
                table_name, store_code = Tool.parse_imsi(imsi, db_info)#parse imsi,return table_name and store_code in database
                row = None
                if not self.sync_imsinum_tag.is_set():
                    row = self.database.query(table_name, store_code)
                if row:
                    true_response_imsi_list.append(imsi)
                else:
                    response_imsi_list.append(imsi)#返回未查询到的imsi列表
        except Exception as e:
            logger.error(e.message)
        #if response_imsi_list is empty, no response
        if response_imsi_list:
            Ubc._response(address, id=RspMsgId_value.ntc_query_imsi_rep,\
            imsilist=response_imsi_list, result='0', boardid=message['boardid'], carrierid=message['carrierid'])
        if true_response_imsi_list:
            Ubc._response(address, id=RspMsgId_value.ntc_query_imsi_rep,\
            imsilist=true_response_imsi_list, result='1', boardid=message['boardid'], carrierid=message['carrierid'])
    dispatch[RcvMsgId_value.ntc_query_imsi] = _process_ntc_query_imsi

    #处理ntc模块上报的插入数据库的消息
    def _process_ntc_insert_imsi(self, message, address):
        """parse imsi and get table_name,store_code ->
        query whether the database has stored the store_code in table named table_name ->
        if not -> insert store_code to table named table_name.
        message:type:dict
        """
        imsi_list = message.get(MsgKey.imsi_list)#imsi is list
        for imsi in imsi_list:
            try:
                table_name, store_code = Tool.parse_imsi(imsi, db_info)
                if self.sync_imsinum_tag.is_set():
                    return None
                row = self.database.query(table_name, store_code)
            except Exception as e:
                logger.error('insert imsi error: %s' % str(e))
                return None
            else:
                if not row:
                    try:
                        if self.sync_imsinum_tag.is_set():
                            return None
                        self.database.insert(table_name, store_code)
                    except Exception as e:
                        logger.error(str(e.args) + str(e.message))
    dispatch[RcvMsgId_value.ntc_insert_imsi] = _process_ntc_insert_imsi

    # 处理ntc模块上报的同步imsinum消息
    def _process_start_sync_imsinum(self, message, address):
        self.sync_imsinum_tag.set()

    dispatch[RcvMsgId_value.ntc_sync_imsi] = _process_start_sync_imsinum


    # 管控模式下对所有的4G上报的IMSI，进行管控，对在白名单的IMSI则无需指派。
    def _process_redirect_imsi(self, response, imsi, address, table_name):
        try:
            white_tag = self.check_fail_imsi_db.query_imsi(imsi, white_table_tag=True)
        except Exception as e:
            logger.error('fail to query white imsi :%s' % str(e))
            white_tag = None
        logger.info('white_tag is:%s' % str(white_tag))
        if white_tag:
            response(address, id=RspMsgId_value.ubc_set_imsi,
                     ubc_info=[[imsi, Ubc.REJECT, arfcn.get(table_name)]])
        else:
            response(address, id=RspMsgId_value.ubc_set_imsi,
                     ubc_info=[[imsi, Ubc.REDIRECT, arfcn.get(table_name)]])

    #处理4G上报的查询IMSI是否需要翻译的消息
    def _process_ubc_get_imsi(self, message, address):
        """process the message packet form client.
        message:type:dict
        address:type:tuple
        """
        response = Ubc._response
        Ubc.report_imsi_num_4G += 1
        logger.debug('message:' + str(message) + 'address:' + str(address))
        logger.debug('received get_imsi_ubc packet, it is ready to send set_imsi_ubc packet')
        imsi = message.get(MsgKey.imsi)
        table_name, store_code = Tool.parse_imsi(imsi, db_info)


        # 如果为电信，则直接拒绝
        if table_name == tele_table_name:
            if self.work_mode in ['2', 2]:
                response(address, id=RspMsgId_value.ubc_set_imsi, ubc_info=[[imsi, Ubc.REDIRECT, 0]])
            else:
                response(address, id=RspMsgId_value.ubc_set_imsi,ubc_info=[[imsi,Ubc.REJECT,0]])
            logger.info("telecom reject directly")
            return
        logger.info('2g_empty_num: %s 4g_empyt_num: %s' % (str((self.mobile_2G_empty_ue_num,self.union_2G_empty_ue_num)),
                                                           str((self.mobile_4G_empty_ue_num,self.union_4G_empty_ue_num))))
        # 特殊的非大陆IMSI 一律拒绝
        if arfcn.get(table_name):
            pass
        else:
            response(address, id=RspMsgId_value.ubc_set_imsi,
                     ubc_info=[[imsi, Ubc.REJECT, 0]])
            return

        # 如果是管控模式则所有的 移动、联通 号码都需要进行指派
        if self.work_mode in ['2', 2]:
            self._process_redirect_imsi(response, imsi, address, table_name)
            logger.info('control imsi')
            return
        # 统计UBC收到的联通移动imsi的数量
        #if table_name == mobile_table_name:
            #Ubc.report_mobile_imsi_num_4G +=1
        #if table_name == union_table_name:
            #Ubc.report_union_imsi_num_4G +=1

        # 移动联通4G翻译模块数量不为0，查询数据库
        try:
            row = None
            fail_tag = None
            if not self.sync_imsinum_tag.is_set():
                row = self._query_database(table_name, store_code)
                try:
                    fail_tag = self.check_fail_imsi_db.query_imsi(imsi)
                except Exception as e:
                    logger.error('fail to check imsi failed to be translated :%s' % str(e))
            # 该号码翻译过，在数据库中能找到记录，给4g设备发送拒绝消息
            if row or fail_tag:
                logger.debug(imsi + ' callnum already translated or translate fail.')
                response(address, id=RspMsgId_value.ubc_set_imsi,
                         ubc_info=[[imsi, Ubc.REJECT, 0]])
                # 该imsi没翻译过，指派到2G
            else:
                logger.debug(imsi + ' callnum NOT translated.')
                # 如果移动联通4G翻译模块数量为0，则直接拒绝
                if self.catpool_num == 2:
                    if (table_name == mobile_table_name and self.mobile_4G_empty_ue_num <= 0) or (
                            table_name == union_table_name and self.union_4G_empty_ue_num <= 0):
                        response(address, id=RspMsgId_value.ubc_set_imsi, ubc_info=[[imsi, Ubc.REJECT_ONCE, 0]])
                        logger.info("No free 4G translation modules are available")
                        return
                elif self.catpool_num == 1:
                    if (table_name == mobile_table_name and self.mobile_2G_empty_ue_num <= 0) or (
                            table_name == union_table_name and self.union_2G_empty_ue_num <= 0):
                        response(address, id=RspMsgId_value.ubc_set_imsi, ubc_info=[[imsi, Ubc.REJECT_ONCE, 0]])
                        logger.info("No free 2G translation modules are available")
                        return
                # 给4g设备发送指派消息
                # 针对非大陆内的手机号做特殊处理

                response(address, id=RspMsgId_value.ubc_set_imsi,
                         ubc_info=[[imsi, Ubc.REDIRECT, arfcn.get(table_name)]])
                # why should imsi be stored into db here.
                # self.database.insert(table_name, store_code)
                # 将指派的imsi发送给2g
                if self.address_2GC is not None:
                    response(self.address_2GC, id=RspMsgId_value.ntc_set_imsi,
                             imsilist=[imsi], modulelist=[table_name])
                # self._ntc_update_empty_ue_num(table_name)
        except Exception as e:
            logger.error(str(e.args) + str(e.message))

    dispatch[RcvMsgId_value.ubc_get_imsi] = _process_ubc_get_imsi

    #处理4G模块上报的心跳包
    def _process_ubc_heartbeat(self, message, address):
        """Processing the heartbeat packet that are reported from the UBC module.
        message:type:dict
        address:type:tuple
        """
        logger.debug('message:' + str(message) + 'address:' + str(address))
        Ubc._response(address, id=RspMsgId_value.ubc_heartbeat_ack, module=MsgKey.ubc)
    dispatch[RcvMsgId_value.ubc_heartbeat] = _process_ubc_heartbeat

    #查询数据库
    def _query_database(self, table_name, store_code):
        """query data from database of table named table_name.
        table_name:type:string
        store_code:type:string
        """
        row = None
        try:
            row = self.database.query(table_name, store_code)  # 根据表名和存储的代码查询数据库
            return row
        except Exception as e:
            logger.error(str(e.args) + str(e.message))
        # return row.fetchone()

    #更新本地记录的2G翻译模块的当前的空闲的数量
    def _ntc_update_empty_ue_num(self, table_name):
        """After assigning the imsi to the translation module and update the number of the free translation
        module.
        table_name:type:string
        """

        if table_name == mobile_table_name:
            if self.mobile_4G_empty_ue_num:
                self.mobile_4G_empty_ue_num -= 1
        elif table_name == union_table_name:
            if self.union_4G_empty_ue_num:
                self.union_4G_empty_ue_num -= 1

    #send message to address use socket
    @classmethod
    def _response(cls, address, **kwargs):
        """send data to client.
        address:type:tuple
        """
        _send = cls.sock.sendto
        packet = {}

        for key,value in kwargs.items():
            packet[key] = value
        _send(json.dumps(packet), address)
        logger.info('send' + str(json.dumps(packet)) + str(address))

    #消息处理，消息分发
    def _process_message(self, message, address):
        """process the message sent by the socket.
        message:message from socket client
        address:address of client
        """
        logger.info('message:' + message + 'address:' + str(address))
        dispatch = self.dispatch
        if message:
            message_dict = json.loads(message)
            id = message_dict.get(MsgKey.id)
            if id in dispatch:
                _func = dispatch.get(id)
                _func(self,message_dict, address)
            else:
                logger.error('unrecognized message from:' + str(address))

    def main_process(self):
        """main process function."""
        try:
            while True:
                # 接收4G和NTC的消息,message是字符,address是消息的发送地址
                message, address = Ubc.sock.recvfrom(Ubc.BUF_SIZE)
                logger.info('receive from client:' + str(len(message)) + 'bytes data')
                self._process_message(message, address)
        except Exception as e:
            logger.exception(e)

#def create_direct():
    #if not os.path.exists('/tmp/log/ubc/'):
        #os.makedirs('/tmp/log/ubc/')
if __name__ == '__main__':
    #create_direct()
    logger.info(VERSION)
    ubc = Ubc('', 6080)
    timer = Timer(60, ubc.func_timer)
    timer.start()
    ubc.main_process()
