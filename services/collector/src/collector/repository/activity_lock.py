from contextlib import contextmanager
from uuid import UUID
from collector.repository.connection import repository_connection

@contextmanager
def simulation_lock(target_id):
    with repository_connection() as conn:
        cursor=conn.cursor()
        resource=f'autotuner:simulation:{UUID(str(target_id))}'
        try:
            row=cursor.execute('''SET NOCOUNT ON; DECLARE @r int;
                EXEC @r=sys.sp_getapplock @Resource=?,@LockMode='Exclusive',@LockOwner='Session',@LockTimeout=0;
                SELECT @r;''',resource).fetchone()
            if row is None or row[0]<0: raise ValueError('A simulator is active for this target. Stop it first.')
            try: yield
            finally: cursor.execute("EXEC sys.sp_releaseapplock @Resource=?,@LockOwner='Session';",resource)
        finally: cursor.close()
