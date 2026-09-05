"""Identity and membership domain types."""

from typing import NewType

UserId = NewType("UserId", str)
UserIdentityId = NewType("UserIdentityId", str)
MembershipId = NewType("MembershipId", str)
