import sys
import uvicorn

if __name__ == "__main__":
    # SageMaker passes "serve" argument
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        uvicorn.run("main:app", host="0.0.0.0", port=8080)
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=8080)