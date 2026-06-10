# Mintlify docs — build from mint-docs/: docker build -t iso-robot-docs .
FROM node:22-alpine

WORKDIR /app

RUN npm install -g mint@latest

COPY . .

ENV PORT=3005
ENV HOSTNAME=0.0.0.0

EXPOSE 3005

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3005').then((r)=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["sh", "-c", "mint dev --port ${PORT} --host 0.0.0.0 --no-open"]
