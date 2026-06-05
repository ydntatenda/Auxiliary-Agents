from app.core.auth_stub import (
    CURRENT_USER_ID,
    MEMBERS,
    ORG_NAME,
    find_member,
    get_current_user,
    get_member,
)


def test_org_constants_present() -> None:
    assert ORG_NAME == "GT Parking & Transportation"
    assert len(MEMBERS) >= 3


def test_current_user_resolves() -> None:
    user = get_current_user()
    assert user.id == CURRENT_USER_ID
    assert user.name


def test_find_member_substring_case_insensitive() -> None:
    hits = find_member("officer")
    ids = {m.id for m in hits}
    assert {"officer_1", "officer_2"}.issubset(ids)


def test_find_member_empty_query_returns_all() -> None:
    assert len(find_member("")) == len(MEMBERS)


def test_get_member_known_and_unknown() -> None:
    assert get_member("tatenda") is not None
    assert get_member("nonexistent") is None
