FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[gmail]"
ENV JOBHUNT_DB=/data/tracker.db HOST=0.0.0.0 PORT=8000
VOLUME /data
EXPOSE 8000
CMD ["jobhunt-mcp", "--transport", "streamable-http"]
