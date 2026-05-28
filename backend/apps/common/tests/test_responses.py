from apps.common.responses import std_response


def test_std_response_success_envelope():
    response = std_response(data={"status": "ok"}, meta={"request_id": "test-request"})

    assert response.status_code == 200
    assert response.data == {
        "ok": True,
        "data": {"status": "ok"},
        "error": None,
        "meta": {"request_id": "test-request"},
    }


def test_std_response_error_envelope():
    response = std_response(
        error={"code": "invalid_input", "message": "Message is required."},
        status=400,
    )

    assert response.status_code == 400
    assert response.data == {
        "ok": False,
        "data": None,
        "error": {"code": "invalid_input", "message": "Message is required."},
        "meta": {},
    }
