"""Cross-process exclusion using a session-owned repository application lock."""
from contextlib import contextmanager
from uuid import UUID

from collector.repository.connection import repository_connection


class CollectionBusyError(ValueError):
    pass


@contextmanager
def target_collection_lock(target_id: UUID):
    resource = f"autotuner:collection:{UUID(str(target_id))}"
    with repository_connection() as connection:
        cursor = connection.cursor()
        try:
            row = cursor.execute(
                """SET NOCOUNT ON;
                DECLARE @result int;
                EXEC @result = sys.sp_getapplock @Resource=?, @LockMode='Exclusive',
                    @LockOwner='Session', @LockTimeout=0;
                SELECT @result;""", resource,
            ).fetchone()
            if row is None or row[0] < 0:
                raise CollectionBusyError("Another collection is running for this target. Try again after it finishes.")
            try:
                yield
            finally:
                cursor.execute("EXEC sys.sp_releaseapplock @Resource=?, @LockOwner='Session';", resource)
        finally:
            cursor.close()
