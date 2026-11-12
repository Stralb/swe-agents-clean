FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /repo
COPY requirements.txt Makefile ./
RUN make setup
COPY . .
CMD ["make", "check"]
