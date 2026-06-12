# pi-agent CLI in a container.
#
#   docker build -t pi-agent .
#   docker run -it --rm -e GROQ_API_KEY -v "$PWD":/work pi-agent
#
# Mount the directory you want the agent to work in at /work; pass whichever
# provider key you use (-e ANTHROPIC_API_KEY, -e GROQ_API_KEY, …).
FROM python:3.12-slim

# git enables the read-only `git` tool inside the container
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir ".[data]"

WORKDIR /work
ENTRYPOINT ["pi"]
