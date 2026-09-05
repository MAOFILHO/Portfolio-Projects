from src.base.login_helper import BaseLoginHelper


class DomainAdapterLoginHelper(BaseLoginHelper):
    def login(self, **kwargs):
        return True
