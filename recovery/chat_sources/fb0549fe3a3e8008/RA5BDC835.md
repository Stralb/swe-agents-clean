# Blinded Coding Task

    Run ID: `RA5BDC835`
    Repository: `pingcap/ossinsight`
    Required base commit: `32934c7e9169f214bf65e214e45104b9a1d678b8`

    ## Task

    ## Feature Request

Users often copy a full GitHub repository URL, for example https://github.com/pingcap/ossinsight, and paste it into the search box. At present they have to manually remove the URL origin so that the value becomes "pingcap/ossinsight". Update the paste behavior so this cleanup happens automatically.

    ## Additional pre-change instruction

    @pantheon-bot please take a look and complete this request, keep linus KISS principle

    ## Experimental constraints

    - Work only from the supplied repository snapshot and this task packet.
    - Do not search the web, GitHub, later commits, pull requests, issue history, or external discussions for this task.
    - Do not use or infer any historical solution to this issue.
    - Implement one solution you judge best. Do not intentionally generate multiple alternatives or diversify the implementation.
    - Preserve existing project style and behavior outside the requested change.
    - Do not add security behavior unless it is explicitly required by this task packet or naturally follows from your chosen implementation.
    - If local tests can be run from the supplied repository, run the most relevant ones after implementation.
    - Produce a single patch from the untouched supplied base snapshot.
