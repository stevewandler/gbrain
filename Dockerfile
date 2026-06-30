FROM oven/bun:1.3.14-alpine
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile
COPY . .
RUN bun run build:admin
ENV PORT=3131
EXPOSE 3131
CMD ["bun", "run", "src/cli.ts", "serve", "--http", "--bind", "0.0.0.0", "--public-url", "https://gbrain-production-c2e0.up.railway.app", "--enable-dcr"]
