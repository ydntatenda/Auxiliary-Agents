"""Hardcoded auth stub.

Replaces what will become a real auth + membership system. Every API
surface that needs to know who the current user is, or look someone up by
name, goes through this module. When real auth lands, only the body of
these helpers changes; the call sites stay put.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Member:
    id: str
    name: str
    role: str  # "admin" or "member"
    avatar: str


ORG_NAME = "GT Parking & Transportation"
ORG_SLUG = "gt-pnt"


MEMBERS: list[Member] = [
    Member(id="tatenda", name="Tatenda Ncube-Muchandibaya", role="admin", avatar="TN"),
    Member(id="chidubem", name="Chidubem Onwuchuluba", role="member", avatar="CO"),
    Member(id="aanya", name="Aanya", role="member", avatar="AA"),
    Member(id="officer_1", name="Officer Williams", role="member", avatar="OW"),
    Member(id="officer_2", name="Officer Chen", role="member", avatar="OC"),
    Member(id="supervisor", name="Supervisor Davis", role="member", avatar="SD"),
]


# Hardcoded "logged in" user. Change this id to simulate logging in as
# someone else, useful for exercising notification flows.
CURRENT_USER_ID = "tatenda"


def get_current_user() -> Member:
    return next(member for member in MEMBERS if member.id == CURRENT_USER_ID)


def find_member(query: str) -> list[Member]:
    """Search members by name substring, case-insensitive.

    Empty query returns everyone, so the autocomplete UI can show the full
    list when the field is focused but empty.
    """
    needle = query.strip().lower()
    if not needle:
        return list(MEMBERS)
    return [member for member in MEMBERS if needle in member.name.lower()]


def get_member(member_id: str) -> Member | None:
    return next((member for member in MEMBERS if member.id == member_id), None)
