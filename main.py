import os
import re
import requests
import hashlib
import time
import copy
import logging
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API_URL
LIKE_URL = "http://c.tieba.baidu.com/c/f/forum/like"
SIGN_URL = "http://c.tieba.baidu.com/c/c/forum/sign"
LOGIN_URL = 'http://c.tieba.baidu.com/c/s/login'

ENV = os.environ

s = requests.Session()

type Params = dict[str, str]
type Json = dict

def gen_sign(param: Params) -> Params:
    if 'sign' in param: # 删除sign
        del param['sign']
    param = dict(sorted(param.items()))
    s: str = ''
    for k, v in param.items():
        s += k + '=' + v
    sign: str = hashlib.md5((s + 'tiebaclient!!!').encode('utf-8')).hexdigest()
    param['sign'] = sign
    return param

def get_tbs(bduss: str) -> str:
    logger.info("获取tbs")
    param = {
        'bdusstoken': bduss,
    }
    param = gen_sign(param)
    try:
        res: Json = s.post(url=LOGIN_URL, data=param, timeout=5).json()
    except Exception as e:
        logger.error(f"获取tbs出错: {e}")
        return ''
    tbs: str = res['anti']['tbs']
    return tbs

def get_favorite(bduss):
    logger.info("获取关注的贴吧")
    param: Params = {
        'BDUSS': bduss,
        '_client_type': '2',
        '_client_id': 'wappc_1534235498291_488',
        '_client_version': '9.7.8.0',
        '_phone_imei': '000000000000000',
        'from': '1008621y',
        'model': 'MI+5',
        'net_type': '1',
        'vcode_tag': '11',
    }
    i: int = 0
    error_num: int = 0
    fav_list: list[dict] = []
    while True:
        i = i + 1
        param['page_no'] = str(i)
        param['timestamp'] = str(int(time.time()))
        param = gen_sign(param)
        try:
            res = s.post(url=LIKE_URL, data=param, timeout=5).json()
        except Exception as e:
            error_num += 1
            if error_num > 3:
                logger.error(f"超出重试次数: {e}")
                return []
            logger.error(f"获取关注的贴吧出错: {e}")
            continue
        if 'forum_list' not in res:
            continue
        if 'non-gconforum' in res['forum_list']:
            fav_list.extend([{'id': f['id'], 'name': f['name']} for f in res['forum_list']['non-gconforum']])
        if 'gconforum' in res['forum_list']:
            fav_list.extend([{'id': f['id'], 'name': f['name']} for f in res['forum_list']['gconforum']])
        if 'has_more' not in res or res['has_more'] != '1':
            break
    return fav_list

def sign_forum(bduss, tbs, fid, kw):
    # 客户端签到
    logger.info(f"开始签到贴吧: {kw}")
    param: Params = {
        'BDUSS': bduss,
        '_client_type': '2',
        '_client_version': '9.7.8.0',
        '_phone_imei': '000000000000000',
        'fid': fid,
        'kw': kw,
        'model': 'MI+5',
        "net_type": "1",
        'tbs': tbs,
        'timestamp': str(int(time.time())),
    }
    param = gen_sign(param)
    res = s.post(url=SIGN_URL, data=param, timeout=5).json()
    return res

def tieba_sign() -> str:
    if 'BDUSS' not in ENV:
        logger.error("未配置BDUSS")
        return '未配置BDUSS'
    logger.info(f"开始贴吧签到")
    b = ENV['BDUSS'].split('#')
    msg: str = ''
    for n, bduss in enumerate(b):
        logger.info(f"开始签到第{n + 1}个用户")
        msg += f"第{n + 1}个用户: \n"
        tbs = get_tbs(bduss) # 每个用户只获取一次tbs
        fav_list = get_favorite(bduss)
        for forum in fav_list:
            time.sleep(random.randint(1,5)) # 防止封号
            res: Json = sign_forum(bduss, tbs, forum['id'], forum['name'])
            msg += f"{forum['name']}: "
            if res['error_code'] == '0':
                ui = res['user_info']
                msg += f"签到成功, 经验+{ui['sign_bonus_point']}! 排名: {ui['user_sign_rank']}, 总共签到{ui['total_sign_num']}天, 连续签到{ui['cont_sign_num']}天\n"
            else:
                msg += f"签到失败, {res['error_msg']}\n"
    logger.info("所有用户签到结束")
    return msg

def sc_send(sendkey, title, desp='', options=None):
    if options is None:
        options = {}
    # 判断 sendkey 是否以 'sctp' 开头，并提取数字构造 URL
    if sendkey.startswith('sctp'):
        match = re.match(r'sctp(\d+)t', sendkey)
        if match:
            num = match.group(1)
            url = f'https://{num}.push.ft07.com/send/{sendkey}.send'
        else:
            raise ValueError('Invalid sendkey format for sctp')
    else:
        url = f'https://sctapi.ftqq.com/{sendkey}.send'
    params = {
        'title': title,
        'desp': desp,
        **options
    }
    headers = {
        'Content-Type': 'application/json;charset=utf-8'
    }
    response = requests.post(url, json=params, headers=headers)
    result = response.json()
    return result

def send_wechat(msg):
    if 'SENDKEY' not in ENV:
        logger.error("未配置SENDKEY")
        return
    key = ENV['SENDKEY']
    ret = sc_send(key, '百度贴吧自动签到', msg)
    logger.info(f"推送微信消息: {ret}")

def main():
    msg = tieba_sign()
    send_wechat(msg)

if __name__ == '__main__':
    main()
