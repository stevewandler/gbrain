FROM oven/bun:1.3.14-alpine
WORKDIR /app

# Install git to clone at build time
RUN apk add --no-cache git

# Clone the exact working commit
RUN git clone https://github.com/stevewandler/gbrain.git /tmp/gbrain && \
    cp -r /tmp/gbrain/* /app/ && \
    cp -r /tmp/gbrain/.git /app/ 2>/dev/null || true && \
    rm -rf /tmp/gbrain && \
    git checkout d135ec7e

# Install deps
RUN bun install --frozen-lockfile && apk del git

ENV PORT=3131
EXPOSE 3131
CMD ["bun", "run", "src/cli.ts", "serve", "--http", "--bind", "0.0.0.0", "--enable-dcr"]
