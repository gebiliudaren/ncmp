from typing import Dict

import requests

from ..utils.config import Config
from ..utils.logger import Logger
from .tasks.daily import DailyTask
from .tasks.extra import ExtraTask


class MusicPartnerBot:
    def __init__(self, config: Config, logger: Logger, session: requests.Session):
        self.config = config
        self.logger = logger
        self.session = session
        self.api = {
            "user_info": "https://music.163.com/api/nuser/account/get",
        }

    def run(self) -> bool:
        try:
            self._verify_user()
            
            # 处理基础评分任务
            daily_task = DailyTask(self.session, self.logger, self.config)
            complete, task_data = daily_task._get_daily_tasks()
            if not complete:
                daily_task._process_tasks(task_data)
            
            # 处理额外评分任务
            extra_task = ExtraTask(self.session, self.logger, self.config)
            extra_task.process_extra_tasks(task_data["id"])
            
            return True
            
        except Exception as e:
            self.logger.error(f"执行失败: {str(e)}")
            return False

    def _verify_user(self) -> None:
        """验证用户信息"""
        try:
            self.logger.info("开始验证用户信息...")
            response = self.session.get(url=self.api["user_info"]).json()
            
            profile = response.get("profile")
            if profile:
                self.logger.info(f'用户名: {profile["nickname"]}')
            else:
                raise RuntimeError("获取用户信息失败")
                
        except Exception as e:
            raise RuntimeError(f"验证用户信息失败: {str(e)}") 
