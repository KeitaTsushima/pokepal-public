import { HubConnectionBuilder, LogLevel } from '@microsoft/signalr';

const NEGOTIATE_URL = 'https://pokepal-realtime-api.azurewebsites.net/api/negotiate';

let connection = null;

/**
 * Establish SignalR connection
 */
export async function connectSignalR() {
  if (connection) {
    console.log('[SignalR] Already connected');
    return connection;
  }

  try {
    // 1. Get connection info from negotiate endpoint
    const response = await fetch(NEGOTIATE_URL);
    if (!response.ok) {
      throw new Error(`negotiate failed: ${response.status}`);
    }
    const { url, accessToken } = await response.json();

    // 2. Build SignalR connection
    connection = new HubConnectionBuilder()
      .withUrl(url, { accessTokenFactory: () => accessToken })
      .configureLogging(LogLevel.Information)
      .withAutomaticReconnect()
      .build();

    // 3. Start connection
    await connection.start();
    console.log('[SignalR] Connected');

    return connection;
  } catch (error) {
    console.error('[SignalR] Connection failed:', error);
    connection = null;
    throw error;
  }
}

/**
 * Disconnect SignalR
 */
export async function disconnectSignalR() {
  if (connection) {
    await connection.stop();
    connection = null;
    console.log('[SignalR] Disconnected');
  }
}

/**
 * Listen to deviceUpdated events
 */
export function onDeviceUpdated(callback) {
  if (!connection) {
    console.warn('[SignalR] Not connected');
    return;
  }

  connection.on('deviceUpdated', callback);
}
