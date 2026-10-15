import pytest
from backend.app.main import app
from backend.app.dependencies import get_current_user


@pytest.fixture(autouse=True)
def override_auth_default():
    """
    Default autouse fixture providing an authenticated adjuster principal
    for existing functional and regression test suites.
    Dedicated security tests can clear or override this fixture.
    """
    app.dependency_overrides[get_current_user] = lambda: {
        "uid": "test-adjuster-1",
        "email": "adjuster@finshield.test",
        "role": "adjuster"
    }
    yield
    app.dependency_overrides.clear()
