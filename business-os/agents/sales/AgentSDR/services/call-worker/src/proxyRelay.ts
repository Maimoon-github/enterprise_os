import { createServer, request as httpRequest, type IncomingMessage, type Server } from "node:http";
import { connect, type AddressInfo, type Socket } from "node:net";
import { SocksClient } from "socks";
import type { WorkerProxy } from "../../../src/lib/calls/stationContract";

/**
 * A local, password-free proxy in front of a number's real proxy.
 *
 * The browser cannot log in to the proxies we buy: Chromium has no SOCKS5
 * authentication (ERR_NO_SUPPORTED_PROXIES), and Playwright's HTTP proxy
 * auth fails against Proxy-Cheap's ISP proxies (ERR_TUNNEL_CONNECTION_FAILED)
 * while curl with the same credentials works — both seen 23 Oct 2026. So
 * the browser talks to 127.0.0.1 with no credentials, and this relay opens
 * each connection through the real proxy with them. The password never
 * reaches the browser.
 *
 * HTTPS (and WebSocket) arrive as CONNECT and become a tunnel through the
 * upstream proxy; plain HTTP requests are forwarded with the upstream's
 * Proxy-Authorization added.
 */
export type ProxyRelay = {
  server: string;
  /** Opens one tunnel to WhatsApp through the upstream proxy; throws its reason (bad password, refused, timeout). */
  check(): Promise<void>;
  /** Bytes carried so far, both directions, by destination host — what the proxy provider bills. */
  usage(): { total: number; byHost: Map<string, number> };
  close(): Promise<void>;
};

export async function startProxyRelay(upstream: WorkerProxy): Promise<ProxyRelay> {
  const url = new URL(upstream.server);
  const upstreamHost = url.hostname;
  const upstreamPort = Number(url.port);
  const socks = url.protocol.startsWith("socks");
  const auth =
    upstream.username || upstream.password
      ? `Basic ${Buffer.from(`${upstream.username ?? ""}:${upstream.password ?? ""}`).toString("base64")}`
      : null;
  const sockets = new Set<Socket>();
  const byHost = new Map<string, number>();
  /** Counts every byte a socket carries in either direction against `host`. */
  const meter = (socket: Socket, host: string) => {
    socket.on("data", (chunk: Buffer) => byHost.set(host, (byHost.get(host) ?? 0) + chunk.length));
  };

  /** A raw TCP connection to host:port, opened through the upstream proxy. */
  async function tunnel(host: string, port: number): Promise<Socket> {
    if (socks) {
      const { socket } = await SocksClient.createConnection({
        proxy: {
          host: upstreamHost,
          port: upstreamPort,
          type: 5,
          ...(upstream.username ? { userId: upstream.username } : {}),
          ...(upstream.password ? { password: upstream.password } : {}),
        },
        destination: { host, port },
        command: "connect",
        timeout: 20_000,
      });
      return socket;
    }
    return new Promise<Socket>((resolve, reject) => {
      const socket = connect(upstreamPort, upstreamHost);
      socket.setTimeout(20_000, () => socket.destroy(new Error("upstream proxy timed out")));
      socket.once("error", reject);
      socket.once("connect", () => {
        socket.write(
          `CONNECT ${host}:${port} HTTP/1.1\r\nHost: ${host}:${port}\r\n${auth ? `Proxy-Authorization: ${auth}\r\n` : ""}\r\n`,
        );
      });
      let head = Buffer.alloc(0);
      const onData = (chunk: Buffer) => {
        head = Buffer.concat([head, chunk]);
        const end = head.indexOf("\r\n\r\n");
        if (end === -1) return;
        socket.off("data", onData);
        const status = head.subarray(0, head.indexOf("\r\n")).toString();
        if (!/^HTTP\/1\.[01] 200/.test(status)) {
          socket.destroy();
          const message = /Proxy-Message: ([^\r]+)/i.exec(head.toString())?.[1];
          reject(new Error(/ 40[17] /.test(status) ? `the proxy rejected its username/password (${message ?? status})` : `the proxy refused the connection (${status})`));
          return;
        }
        socket.setTimeout(0);
        const rest = head.subarray(end + 4);
        if (rest.length) socket.unshift(rest);
        resolve(socket);
      };
      socket.on("data", onData);
    });
  }

  const server: Server = createServer((req: IncomingMessage, res) => {
    // Plain HTTP: the request line carries the absolute URL.
    let target: URL;
    try {
      target = new URL(req.url ?? "");
    } catch {
      res.writeHead(400).end();
      return;
    }
    if (socks) {
      // Through SOCKS, an HTTP request is just bytes on a tunnel to the origin.
      void tunnel(target.hostname, Number(target.port) || 80).then(
        (socket) => {
          meter(socket, target.hostname);
          const headers = Object.entries(req.headers)
            .filter(([name]) => !/^proxy-/i.test(name))
            .map(([name, value]) => `${name}: ${Array.isArray(value) ? value.join(", ") : value}`)
            .join("\r\n");
          socket.write(`${req.method} ${target.pathname}${target.search} HTTP/1.1\r\n${headers}\r\n\r\n`);
          req.pipe(socket);
          socket.pipe(res.socket!);
        },
        () => res.writeHead(502).end(),
      );
      return;
    }
    const forward = httpRequest(
      {
        host: upstreamHost,
        port: upstreamPort,
        method: req.method,
        path: req.url,
        headers: { ...req.headers, ...(auth ? { "proxy-authorization": auth } : {}) },
      },
      (upstreamRes) => {
        res.writeHead(upstreamRes.statusCode ?? 502, upstreamRes.headers);
        upstreamRes.pipe(res);
      },
    );
    forward.on("error", () => res.writeHead(502).end());
    req.pipe(forward);
  });

  server.on("connect", (req: IncomingMessage, client: Socket, head: Buffer) => {
    const [host, portText] = (req.url ?? "").split(":");
    const port = Number(portText) || 443;
    sockets.add(client);
    client.on("close", () => sockets.delete(client));
    client.on("error", () => client.destroy());
    tunnel(host!, port).then(
      (upstreamSocket) => {
        sockets.add(upstreamSocket);
        meter(upstreamSocket, host!);
        meter(client, host!);
        upstreamSocket.on("close", () => sockets.delete(upstreamSocket));
        upstreamSocket.on("error", () => client.destroy());
        client.write("HTTP/1.1 200 Connection Established\r\n\r\n");
        if (head.length) upstreamSocket.write(head);
        upstreamSocket.pipe(client);
        client.pipe(upstreamSocket);
      },
      () => {
        client.end("HTTP/1.1 502 Bad Gateway\r\n\r\n");
      },
    );
  });

  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  return {
    server: `http://127.0.0.1:${port}`,
    check: async () => {
      const socket = await tunnel("web.whatsapp.com", 443);
      socket.destroy();
    },
    usage: () => ({ total: [...byHost.values()].reduce((sum, n) => sum + n, 0), byHost }),
    close: () =>
      new Promise<void>((resolve) => {
        for (const socket of sockets) socket.destroy();
        server.close(() => resolve());
      }),
  };
}
