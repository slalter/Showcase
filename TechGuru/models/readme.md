Session management:
Each method that uses a session should be passed a session.
Each celery task or app route should start its own session with Session(), and then pass it through.
In the case of exceptionally long-running tasks, it is okay to remake the session, but do so at the top-level of the celery task or app route.

In the case of a multithreaded environment, it is crucial that the session object is not passed to any of the threads. If a thread needs its own session, it should use Session() to make one and should handle the session all the way to its close. Even if the threads exist inside a with session: block, the session will still be preserved as long as the session is not passed to any of the threads, but beware of data staleness, branching session object states, and potential deadlocks.