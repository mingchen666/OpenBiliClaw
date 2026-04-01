const DEFAULT_BACKEND_URL = "http://127.0.0.1:8420/api";

export function createRuntimeStreamUrl(backendUrl = DEFAULT_BACKEND_URL) {
  const base = backendUrl.replace(/\/$/, "");
  if (base.startsWith("https://")) {
    return `${base.replace("https://", "wss://")}/runtime-stream`;
  }
  return `${base.replace("http://", "ws://")}/runtime-stream`;
}

export function createRuntimeStreamClient({
  backendUrl = DEFAULT_BACKEND_URL,
  WebSocketImpl = globalThis.WebSocket,
  reconnectDelayMs = 2000,
  onEvent = () => {},
  onConnect = () => {},
  onDisconnect = () => {},
} = {}) {
  let socket = null;
  let reconnectTimer = null;
  let stopped = false;
  let wasConnected = false;

  function scheduleReconnect() {
    if (stopped || reconnectTimer != null) {
      return;
    }
    reconnectTimer = globalThis.setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, reconnectDelayMs);
  }

  function connect() {
    if (stopped || typeof WebSocketImpl !== "function") {
      return;
    }
    socket = new WebSocketImpl(createRuntimeStreamUrl(backendUrl));
    socket.onopen = () => {
      wasConnected = true;
      onConnect();
    };
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        onEvent(payload);
      } catch {
        // Ignore malformed payloads and keep the stream alive.
      }
    };
    socket.onclose = () => {
      socket = null;
      if (wasConnected) {
        wasConnected = false;
        onDisconnect();
      }
      scheduleReconnect();
    };
  }

  function disconnect() {
    stopped = true;
    if (reconnectTimer != null) {
      globalThis.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    socket?.close?.();
    socket = null;
  }

  return {
    connect,
    disconnect,
  };
}
