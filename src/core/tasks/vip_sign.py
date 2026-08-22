from ..signer import Signer
from .base import BaseTask


class VipSignTask(BaseTask):
    """黑胶乐签：调用网易云 weapi 的 /vip/sign 完成黑胶会员每日乐签。

    仅依赖登录 Cookie（MUSIC_U / __csrf），复用 Signer 做 weapi 加密。
    """

    def __init__(self, session, logger, config):
        super().__init__(session, logger, config)
        self.sign_url = "https://music.163.com/weapi/vip/sign"
        self.signer = Signer(session, "", logger, config)

    def execute(self) -> bool:
        try:
            csrf = str(self.session.cookies["__csrf"])

            data = {"csrf_token": csrf}
            params = {
                "params": self.signer._get_params(data),
                "encSecKey": self.signer._get_enc_sec_key(),
            }

            response = self.session.post(
                url=f'{self.sign_url}?csrf_token={csrf}',
                data=params,
            ).json()

            code = response.get("code")
            if code == 200:
                self.logger.info(f"黑胶乐签成功: {response}")
                return True

            msg = response.get("message") or response.get("msg") or "未知原因"
            self.logger.warning(f"黑胶乐签未成功: code={code} msg={msg}")
            return False

        except Exception as e:
            self.logger.error(f"黑胶乐签执行异常: {str(e)}")
            return False