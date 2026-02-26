FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev
COPY etc/ ./etc/

ENV MCP_TRANSPORT=streamable-http
ENV MCP_PORT=8000
EXPOSE 8000

CMD ["uv", "run", "routeros-mcp"]
