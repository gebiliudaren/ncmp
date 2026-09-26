import base64
import codecs
import json
import random
import re
import string
import time
from typing import Tuple

import requests
from Crypto.Cipher import AES

from ..utils.config import Config
from ..utils.logger import Logger


class Signer:
    def __init__(self, session: requests.Session, task_id: str, logger: Logger, config: Config):
        self.session = session
        self.task_id = task_id
        self.logger = logger
        self.config = config
        self.sign_url = "https://interface.music.163.com/weapi/music/partner/work/evaluate"
        
        # 加密相关常量
        self.random_str = self._generate_random_string(16)
        self.pub_key = "010001"
        self.modulus = "00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7"
        self.iv = "0102030405060708"
        self.aes_key = "0CoJUm6Qyw8W8jud"
        
        self.name_pattern = re.compile('.*[a-zA-Z].*')

    def _generate_random_string(self, length: int) -> str:
        """生成指定长度的随机字符串"""
        return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

    def _add_to_16(self, text: str) -> bytes:
        """将字符串补充到16的倍数"""
        pad = 16 - len(text) % 16
        text = text + chr(pad) * pad
        return text.encode('utf-8')

    def _aes_encrypt(self, text: str, key: str) -> str:
        """AES加密"""
        encryptor = AES.new(key.encode('utf-8'), AES.MODE_CBC, self.iv.encode('utf-8'))
        encrypt_text = encryptor.encrypt(self._add_to_16(text))
        return base64.b64encode(encrypt_text).decode('utf-8')

    def _get_params(self, data: dict) -> str:
        """获取加密后的参数"""
        text = json.dumps(data)
        params = self._aes_encrypt(text, self.aes_key)
        params = self._aes_encrypt(params, self.random_str)
        return params

    def _get_enc_sec_key(self) -> str:
        """获取加密密钥"""
        text = self.random_str[::-1]
        rs = int(codecs.encode(text.encode('utf-8'), 'hex_codec'), 16)
        rs = pow(rs, int(self.pub_key, 16), int(self.modulus, 16))
        return format(rs, 'x').zfill(256)

    def _get_score_and_tag(self, work: dict) -> Tuple[str, str]:
        """根据作品信息获取评分和标签"""
        # 获取评分策略，默认为4（3-4分）
        score_strategy = int(self.config.get("score", 3))
        
        # 检查名称中是否包含英文
        has_english = bool(self.name_pattern.match(work["name"] + work["authorName"]))
        
        # 根据策略和名称决定评分
        if score_strategy == 1:  # 1-2分策略
            score = "2" if has_english else "1"
        elif score_strategy == 2:  # 2-3分策略
            score = "3" if has_english else "2"
        elif score_strategy == 3:  # 2,4分策略（默认）
            score = "4" if has_english else "2"
        else:  # 1,2,4分
            score = "4"
            
        return score, f"{score}-A-1"

    def sign(self, work: dict, is_extra: bool = False) -> None:
        """为作品评分"""
        try:
            # 使用配置的等待时间
            delay = self.config.get_wait_time()
            self.logger.info(f"等待 {delay:.1f} 秒后继续...")
            time.sleep(delay)

            csrf = str(self.session.cookies["__csrf"])
            score, tag = self._get_score_and_tag(work)
            
            data = {
                "taskId": self.task_id,
                "workId": work['id'],
                "score": score,
                "tags": tag,
                "customTags": "%5B%5D",
                "comment": "",
                "syncYunCircle": "true",
                "csrf_token": csrf
            }
            
            # 额外任务需要添加标记
            if is_extra:
                data["extraResource"] = "true"
            
            params = {
                "params": self._get_params(data),
                "encSecKey": self._get_enc_sec_key()
            }
            
            self.logger.debug(f"评分请求数据: {data}")
            
            response = self.session.post(
                url=f'{self.sign_url}?csrf_token={csrf}',
                data=params
            ).json()
            
            self.logger.debug(f"评分响应数据: {response}")
            
            if response["code"] == 200:
                self.logger.info(f'{work["name"]}「{work["authorName"]}」评分完成：{score}分')
            else:
                error_msg = response.get('message') or response.get('msg', '未知错误')
                if "频繁" in error_msg:
                    retry_delay = self.config.get_wait_time()
                    self.logger.info(f"遇到频率限制，等待 {retry_delay:.1f} 秒后重试...")
                    time.sleep(retry_delay)
                    self.sign(work, is_extra)
                elif response["code"] == 405 and "资源状态异常" in error_msg:
                    self.logger.warning(f'歌曲「{work["name"]}」资源状态异常，跳过')
                else:
                    raise RuntimeError(f"评分失败: {error_msg} (响应码: {response.get('code')})")
                
        except Exception as e:
            self.logger.error(f'歌曲「{work["name"]}」评分异常：{str(e)}')
            raise RuntimeError(f"评分过程出错: {str(e)}") 
