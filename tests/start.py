import os
import uvicorn

if __name__ == "__main__":
    os.environ["DOPPLER_ENV"] = "1"
    os.environ["HOST"] = "0.0.0.0"
    os.environ["PORT"] = "8001"
    os.environ["STAGE"] = "local"
    reload = bool(int(os.getenv("RELOAD", 1)))
    uvicorn.run(
        "tests.for_docs.movies_qb:app",
        # "tests.for_docs.movies_edgedb:app",
        host=os.environ["HOST"],
        port=int(os.environ["PORT"]),
        reload=reload,
        log_level="info",
    )
