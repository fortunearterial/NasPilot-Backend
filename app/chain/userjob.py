import pickle

from app.chain import ChainBase
from app.chain.download import DownloadChain
from app.core.config import settings
from app.db.userjob_oper import UserJobOper
from app.utils.singleton import Singleton


class UserJobChain(ChainBase, metaclass=Singleton):
    """
    用户任务处理链
    """

    def __init__(self):
        super().__init__()
        self.userjoboper = UserJobOper()

    def user_job(self):
        jobs = self.userjoboper.consume(settings.CURRENT_USERID)
        for job in jobs:
            job_args = pickle.loads(job.job_args)
            try:
                if job.job_name == "download":
                    DownloadChain().download_single_job(**job_args.get("kwargs"))
            except Exception as e:
                continue
            self.userjoboper.done(job.job_id, settings.CURRENT_USERID)
