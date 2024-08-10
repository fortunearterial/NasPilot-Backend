from app.log import logger

class DebuggerHelper:
    __logs: dict = {}

    _msg: str = None

    @staticmethod
    def get(id: str):
        if not hasattr(id, DebuggerHelper.__logs):
            DebuggerHelper.__logs.put(id, DebuggerHelper())
        return DebuggerHelper.__logs.get(id)

    def __init__(self):
        self._msg = []

    def next(msg: str):
        self._msg.add(msg)

    def prev():
        self._msg.delete(self._msg[-1])


    def log(self, msg: str, *args, **kwargs):
        """
        重载debug方法
        """
        logger.logger("debug", self._msg.join('==>') + '    ' + msg, *args, **kwargs)

if __name__ == "__main":
    DebuggerHelper.get('123').log('asd')
    DebuggerHelper.get('123').next('f1')
    DebuggerHelper.get('123').log('sdf')
    DebuggerHelper.get('123').next('f2')
    DebuggerHelper.get('123').log('dfg')
    DebuggerHelper.get('123').prev()
    DebuggerHelper.get('123').log('dfg')
    DebuggerHelper.get('123').prev()
    DebuggerHelper.get('123').log('sdf')
