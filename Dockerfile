FROM oven/bun:1.3.14-alpine
WORKDIR /app

RUN apk add --no-cache git && \
    git clone --depth 1 --branch dockerfile-deploy \
    https://github.com/stevewandler/gbrain.git /tmp/gbrain && \
    cp -r /tmp/gbrain/* /app/ && \
    rm -rf /tmp/gbrain && \
    bun install --frozen-lockfile && \
    apk del git

# Railway injects PORT at runtime; gbrain reads it.
# Default to 3131 for local testing.
ENV PORT=3131
EXPOSE 3131

# Exact same command as the working June 21 deploy
CMD ["bun", "run", "src/cli.ts", "serve", "--http", "--bind", "0.0.0.0", "--public-url", "https://gbrain-production-c2e0.up.railway.app", "--enable-dcr"]
