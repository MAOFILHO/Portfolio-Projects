from __future__ import annotations

from unittest.mock import MagicMock, patch

from auth import GoogleTokenManager


def _fake_response(access_token: str, expires_in: int = 3600):
    response = MagicMock()
    response.json.return_value = {"access_token": access_token, "expires_in": expires_in}
    response.raise_for_status.return_value = None
    return response


@patch("auth.requests.post")
def test_fetches_token_on_first_call(mock_post):
    mock_post.return_value = _fake_response("token-1")
    manager = GoogleTokenManager("client-id", "client-secret", "refresh-token")

    token = manager.get_access_token()

    assert token == "token-1"
    mock_post.assert_called_once()


@patch("auth.requests.post")
def test_caches_token_until_expiry(mock_post):
    mock_post.return_value = _fake_response("token-1")
    manager = GoogleTokenManager("client-id", "client-secret", "refresh-token")

    manager.get_access_token()
    manager.get_access_token()

    mock_post.assert_called_once()


@patch("auth.requests.post")
def test_refreshes_after_expiry(mock_post):
    mock_post.side_effect = [_fake_response("token-1", expires_in=0), _fake_response("token-2")]
    manager = GoogleTokenManager("client-id", "client-secret", "refresh-token")

    first = manager.get_access_token()
    second = manager.get_access_token()

    assert first == "token-1"
    assert second == "token-2"
    assert mock_post.call_count == 2
