const WEBSOCKET_HOST = process.env.REACT_APP_WEBSOCKET_HOST || 'localhost';
const WEBSOCKET_PORT = process.env.REACT_APP_WEBSOCKET_PORT || 8765;

const WEBSOCKET_URL = `ws://${WEBSOCKET_HOST}:${WEBSOCKET_PORT}`;

export const connectWebSocket = (onMessage) => {
  const socket = new WebSocket(WEBSOCKET_URL);

  socket.onopen = () => {
    console.log('WebSocket connected');
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data);
  };

  socket.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  socket.onclose = () => {
    console.log('WebSocket disconnected');
  };

  return socket;
};

export const sendWebSocketMessage = (socket, message) => {
  if (socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message));
  } else {
    console.error('WebSocket is not open. Unable to send message.');
  }
};