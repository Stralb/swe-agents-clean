from __future__ import annotations

import os
import random
import socket
import time

from src.distributed.spool import DistributedSpool


def main() -> None:
    root = os.environ["DISTRIBUTED_SPOOL_ROOT"]
    pool = os.environ.get(
        "DISTRIBUTED_POOL",
        "test",
    )

    label = os.environ.get(
        "DISTRIBUTED_WORKER_LABEL",
        "worker",
    )

    worker_id = (
        f"{label}-"
        f"{os.getenv('SLURM_JOB_ID', 'local')}-"
        f"{socket.gethostname()}-"
        f"{os.getpid()}"
    )

    spool = DistributedSpool(root)

    processed = 0

    spool.heartbeat(
        pool,
        worker_id,
        state="starting",
        detail="Cross-node spool test starting",
    )

    while True:
        claim = spool.claim(
            pool,
            worker_id,
        )

        if claim is None:
            break

        payload = claim.payload.get(
            "payload",
            {},
        )

        time.sleep(
            random.uniform(
                0.01,
                0.08,
            )
        )

        spool.publish_result(
            claim,
            {
                "value": payload.get("value"),
                "worker_label": label,
                "hostname": socket.gethostname(),
            },
        )

        processed += 1

    spool.heartbeat(
        pool,
        worker_id,
        state="stopped",
        detail=f"Processed {processed} tasks",
    )

    print(
        f"worker={worker_id} "
        f"processed={processed}",
        flush=True,
    )


if __name__ == "__main__":
    main()
