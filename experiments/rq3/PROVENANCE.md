# Provenance

Every file under `jobs/` is a byte-for-byte copy of the script as it existed in the private working archive of the cluster research directory (`mcp_uploads/jobs/<job-folder>/<file>`). The folder names below are the original job-folder names. The table lists each file's size and SHA-256 so the copies can be checked against the cluster originals.

Which script version belongs to which run was identified by the author. The following are consistent with each other: the aggregator requires 12 + 14 + 14 conditions and CodeQL 2.25.6, reads scan results from jobs 71159 (O), 71209 (W) and 71204 (P), and its launcher depends on job 71209. The W scan's launcher depends on jobs 71208 and 71204.

| File | Bytes | SHA-256 |
|---|---:|---|
| `jobs/owp14_20261018_v1/freeze14.py` | 12407 | `1b10095a17625ba71482b6089bb48b7228f698d34e6772e0316e6e99333ce63e` |
| `jobs/owp14_20261018_v1/freeze14_biggpu.sbatch` | 240 | `3f9d5b84b3e3931fbc820507e7eb4b3bd98b610351cf4c3dde73be495002d7ca` |
| `jobs/owp14_20261018_v2/target_index_fix.py` | 2236 | `15a9d891045a0f20649bf875a5e21332ba3f33f5f444f8687c42777157ff9d08` |
| `jobs/owp14_20261018_v2/target_index_fix_biggpu.sbatch` | 286 | `24043469882f12bf800f096c86859a18f3bc4a6de2fb0239ff11427ef9aea15c` |
| `jobs/owp14_user12_20261018_v1/preflight.py` | 6239 | `6995a12954f8a8168c453c1bce9ccb0996598169b366686030f006a9414d1c77` |
| `jobs/owp14_user12_20261018_v1/preflight_biggpu.sbatch` | 355 | `292df0782a929a8759e8a10367b3a40a5a16143599039bb94d5467c6fa1d9b97` |
| `jobs/owp14_user12_20261018_v2/scan12.py` | 11430 | `fb83315e24181544c15617332e5e705fc35bf7b934a7e96b31f90c1d75e93a0e` |
| `jobs/owp14_user12_20261018_v2/scan12_biggpu.sbatch` | 406 | `254192a0d65064da58c1cb8aeeb10516570760ad87b27b47a6279fc0e1b29681` |
| `jobs/owp14_user14_p_20261018_v1/preflight.py` | 6260 | `053d67f991635c2b6fdff63185f40155a9308b191e099e5de44450b5dead5d77` |
| `jobs/owp14_user14_p_20261018_v1/preflight_biggpu.sbatch` | 359 | `f40417b99bc5aac7e8a494216de4720826b40b54cccb147a3bf729d8129b0edf` |
| `jobs/owp14_user14_p_20261018_v2b/preflight.py` | 4797 | `1699de8151282cc961f23e8cde43fb4284b3011d788d45c205fcaad5e0bef07f` |
| `jobs/owp14_user14_p_20261018_v4/scan14.py` | 11712 | `4b5e8ddbeef35babee2dc470515b05c9d670a1fb50cd6316333392c1a75bd3ac` |
| `jobs/owp14_user14_p_20261018_v4/scan14_biggpu.sbatch` | 410 | `cfca8d27085eb11da67e15d764288d3cd4f36ada0eecbb1fa8d3aa517ad402d4` |
| `jobs/owp14_user14_w_20261018_v1/preflight.py` | 4796 | `5e4209a692a17c8c34b502843a8804d57d288cbcfcaff3b041f7959b3a6fde95` |
| `jobs/owp14_user14_w_20261018_v1/preflight_biggpu.sbatch` | 359 | `8baa919266f22da6e58b084a705666d5bf22aa95964ae00834c8d0bf6ddac4d0` |
| `jobs/owp14_user14_w_20261018_v2/scan14.py` | 11712 | `753bae8f1e9730d393309cbc3bb2077927f776a4a41a8b20d44a50dbba70de6e` |
| `jobs/owp14_user14_w_20261018_v2/scan14_biggpu_after_preflight_p.sbatch` | 451 | `13c0814048118901464d4c0e94d7aba3608199492dd5254182f92761b18d98b7` |
| `jobs/owp14_w14_20261018_v3/aggregate_owp.py` | 8560 | `c6050d1778165d55ee8c673c88b0c2ddb8c963b3c1b7b6d86aa8c72be8b083e6` |
| `jobs/owp14_w14_20261018_v3/aggregate_owp_biggpu.sbatch` | 387 | `bfa410fc8d9dadef4469c5ad71577752dd6807a5ad3e0da8e37ed28299474d8e` |
