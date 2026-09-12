"""Print the matching payload for a round, without writing anything.

Read-only. Builds exactly what a matching run would be given, so it is also the
way to look at a round before committing to an hour of scoring.

    bazel run //tools:dump_matching_payload -- --list-rounds
    bazel run //tools:dump_matching_payload -- --round-id 12
    bazel run //tools:dump_matching_payload -- --round-id 12 --user-ids 4,7,9
    bazel run //tools:dump_matching_payload -- --round-id 12 --out /tmp/payload.json

With no --user-ids it takes everyone registered for the round, which is what an
admin selecting all of them would produce.
"""

import argparse
import asyncio
import json
import sys

from sqlalchemy import func, select

from backend.common.database import Database
from backend.common.logger import get_logger
from backend.entity.mentorship_round_entity import MentorshipRoundEntity
from backend.entity.mentorship_round_participants_entity import (
    MentorshipRoundParticipantsEntity,
)
from backend.mentorship.matching_payload_service import MatchingPayloadService
from backend.repository.mentorship_pairs_repository import MentorshipPairsRepository
from backend.repository.mentorship_round_participants_repository import (
    MentorshipRoundParticipantsRepository,
)

logger = get_logger()


def _database_summary(database: Database) -> str:
    """Host and database name, so it is obvious which one this is reading."""
    url = database.get_engine().url
    return f"{url.host}/{url.database}"


async def _print_rounds(session) -> None:
    """Every round with how many people registered, newest id first."""
    result = await session.execute(
        select(
            MentorshipRoundEntity.round_id,
            MentorshipRoundEntity.name,
            func.count(MentorshipRoundParticipantsEntity.user_id),
        )
        .outerjoin(
            MentorshipRoundParticipantsEntity,
            MentorshipRoundEntity.round_id
            == MentorshipRoundParticipantsEntity.round_id,
        )
        .group_by(MentorshipRoundEntity.round_id, MentorshipRoundEntity.name)
        .order_by(MentorshipRoundEntity.round_id.desc())
    )
    for round_id, name, registered in result.all():
        sys.stdout.write(f"{round_id}\t{registered} registered\t{name}\n")


async def _round_name(session, round_id: int) -> str | None:
    result = await session.execute(
        select(MentorshipRoundEntity.name).where(
            MentorshipRoundEntity.round_id == round_id
        )
    )
    return result.scalar_one_or_none()


async def _registered_user_ids(session, round_id: int) -> list[int]:
    result = await session.execute(
        select(MentorshipRoundParticipantsEntity.user_id).where(
            MentorshipRoundParticipantsEntity.round_id == round_id
        )
    )
    return list(result.scalars().all())


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round-id", type=int, default=None)
    parser.add_argument(
        "--list-rounds", action="store_true", help="show rounds and stop"
    )
    parser.add_argument(
        "--user-ids",
        default=None,
        help="comma separated; default is everyone registered for the round",
    )
    parser.add_argument("--out", default=None, help="file to write; default stdout")
    args = parser.parse_args()

    database = Database(echo=False)
    # Which database this is reading is the first thing worth knowing, and a
    # shell DATABASE_URL has pointed somewhere unexpected before.
    logger.info("Reading %s", _database_summary(database))

    try:
        async with database.session() as session:
            if args.list_rounds:
                await _print_rounds(session)
                return
            if args.round_id is None:
                raise SystemExit("Give --round-id, or --list-rounds to find one.")

            name = await _round_name(session, args.round_id)
            if name is None:
                raise SystemExit(f"Round {args.round_id} does not exist here.")
            logger.info("Round %s: %s", args.round_id, name)

            if args.user_ids:
                user_ids = [
                    int(part) for part in args.user_ids.split(",") if part.strip()
                ]
            else:
                user_ids = await _registered_user_ids(session, args.round_id)
                logger.info("Taking all %d registered participants", len(user_ids))
            if not user_ids:
                raise SystemExit(f"Round {args.round_id} has no participants.")

            service = MatchingPayloadService(
                mentorship_round_participants_repository=MentorshipRoundParticipantsRepository(),
                mentorship_pairs_repository=MentorshipPairsRepository(),
                logger=logger,
            )
            payload = await service.build_matching_payload(
                session, args.round_id, user_ids
            )
    finally:
        await database.close()

    text = json.dumps(
        json.loads(payload.model_dump_json()), ensure_ascii=False, indent=2
    )
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        logger.info("Wrote %s", args.out)
    else:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    asyncio.run(main())
