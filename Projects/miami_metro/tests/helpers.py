import mock
import threading


class ServerRunner(object):

    def __init__(self):
        self.mocks = {}
        self.patches = []

    def mock_fn(self, name):
        _mock = mock.MagicMock()
        self.mocks[name] = _mock
        patch = mock.patch(name, new=_mock)
        self.patches.append(patch)
        patch.start()

    def mock_called(self, name):
        called = self.mocks[name].called
        self.mocks[name].reset_mock()
        return called

    def run(self):
        from django.test.utils import override_settings

        @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                           CELERY_ALWAYS_EAGER=True,
                           BROKER_BACKEND='memory',)
        def server_runner_inner():
            from django.core.management.commands.runserver import BaseRunserverCommand
            cmd = BaseRunserverCommand()
            cmd.execute(use_threading=False)

        th = threading.Thread(target=server_runner_inner)
        th.daemon = True
        th.start()
