/**
 * WebSocket Stream Manager
 * 
 * Replaces HTTP MJPEG streaming with WebSocket-based streaming
 * ✅ Proper disconnect detection
 * ✅ Auto-reconnect on connection loss
 * ✅ Clean resource management
 */

export interface StreamConfig {
  url: string;
  userId?: string;
  conf?: number;
  showLabels?: boolean;
  fps?: number;
  skipFrames?: number;
  autoReconnect?: boolean;
  reconnectDelay?: number;
}

export interface StreamStats {
  processed: number;
  skipped: number;
  total: number;
  fps?: number;
}

export type StreamMessageHandler = (imageData: string) => void;
export type StatsHandler = (stats: StreamStats) => void;
export type ErrorHandler = (error: string) => void;
export type ConnectionHandler = () => void;

export class WebSocketStreamManager {
  private ws: WebSocket | null = null;
  private config: Required<StreamConfig>;
  private isConnecting = false;
  private shouldReconnect = true;
  private reconnectTimeout: number | null = null;
  
  // Event handlers
  private onFrameHandler: StreamMessageHandler | null = null;
  private onStatsHandler: StatsHandler | null = null;
  private onErrorHandler: ErrorHandler | null = null;
  private onConnectHandler: ConnectionHandler | null = null;
  private onDisconnectHandler: ConnectionHandler | null = null;

  constructor(config: StreamConfig) {
    this.config = {
      url: config.url,
      userId: config.userId || '',
      conf: config.conf || 0.25,
      showLabels: config.showLabels !== false,
      fps: config.fps || 10,
      skipFrames: config.skipFrames || 2,
      autoReconnect: config.autoReconnect !== false,
      reconnectDelay: config.reconnectDelay || 2000,
    };
  }

  /**
   * Connect to WebSocket stream
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.isConnecting) {
      console.warn('[WebSocketStream] Already connected or connecting');
      return;
    }

    this.isConnecting = true;
    this.shouldReconnect = true;

    // Build WebSocket URL with query params
    const url = new URL(this.config.url);
    if (this.config.userId) url.searchParams.set('user_id', this.config.userId);
    url.searchParams.set('conf', this.config.conf.toString());
    url.searchParams.set('show_labels', this.config.showLabels.toString());
    url.searchParams.set('fps', this.config.fps.toString());
    url.searchParams.set('skip_frames', this.config.skipFrames.toString());

    console.log('[WebSocketStream] Connecting to:', url.toString());

    try {
      this.ws = new WebSocket(url.toString());

      this.ws.onopen = () => {
        console.log('[WebSocketStream] ✅ Connected');
        this.isConnecting = false;
        if (this.onConnectHandler) this.onConnectHandler();
      };

      this.ws.onmessage = (event) => {
        try {
          // Check if message is JSON (stats/error) or base64 (frame)
          if (event.data.startsWith('{')) {
            const msg = JSON.parse(event.data);
            
            if (msg.type === 'frame' && this.onFrameHandler) {
              this.onFrameHandler(msg.data);
            } else if (msg.type === 'stats' && this.onStatsHandler) {
              this.onStatsHandler({
                processed: msg.processed,
                skipped: msg.skipped,
                total: msg.total,
                fps: msg.fps,
              });
            } else if (msg.type === 'error' && this.onErrorHandler) {
              this.onErrorHandler(msg.message);
            }
          } else {
            // Raw base64 frame (for /ws/stream/raw endpoint)
            if (this.onFrameHandler) {
              this.onFrameHandler(event.data);
            }
          }
        } catch (error) {
          console.error('[WebSocketStream] Message parse error:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('[WebSocketStream] ❌ WebSocket error:', error);
        if (this.onErrorHandler) {
          this.onErrorHandler('WebSocket connection error');
        }
      };

      this.ws.onclose = (event) => {
        console.log('[WebSocketStream] 🔴 Disconnected:', event.code, event.reason);
        this.isConnecting = false;
        this.ws = null;
        
        if (this.onDisconnectHandler) this.onDisconnectHandler();

        // Auto-reconnect if enabled
        if (this.shouldReconnect && this.config.autoReconnect) {
          console.log(`[WebSocketStream] Reconnecting in ${this.config.reconnectDelay}ms...`);
          this.reconnectTimeout = window.setTimeout(() => {
            this.connect();
          }, this.config.reconnectDelay);
        }
      };
    } catch (error) {
      console.error('[WebSocketStream] Connection failed:', error);
      this.isConnecting = false;
      if (this.onErrorHandler) {
        this.onErrorHandler('Failed to create WebSocket connection');
      }
    }
  }

  /**
   * Disconnect from WebSocket stream
   */
  disconnect(): void {
    console.log('[WebSocketStream] Manually disconnecting...');
    this.shouldReconnect = false;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      // Close WebSocket (triggers onclose handler)
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.isConnecting = false;
  }

  /**
   * Update stream configuration
   */
  updateConfig(newConfig: Partial<StreamConfig>): void {
    const needsReconnect = 
      (newConfig.url && newConfig.url !== this.config.url) ||
      (newConfig.userId && newConfig.userId !== this.config.userId) ||
      (newConfig.conf !== undefined && newConfig.conf !== this.config.conf) ||
      (newConfig.fps !== undefined && newConfig.fps !== this.config.fps) ||
      (newConfig.skipFrames !== undefined && newConfig.skipFrames !== this.config.skipFrames);

    // Update config
    Object.assign(this.config, newConfig);

    // Reconnect if parameters changed
    if (needsReconnect && this.ws?.readyState === WebSocket.OPEN) {
      console.log('[WebSocketStream] Config changed, reconnecting...');
      this.disconnect();
      setTimeout(() => this.connect(), 100);
    }
  }

  /**
   * Event handlers
   */
  onFrame(handler: StreamMessageHandler): void {
    this.onFrameHandler = handler;
  }

  onStats(handler: StatsHandler): void {
    this.onStatsHandler = handler;
  }

  onError(handler: ErrorHandler): void {
    this.onErrorHandler = handler;
  }

  onConnect(handler: ConnectionHandler): void {
    this.onConnectHandler = handler;
  }

  onDisconnect(handler: ConnectionHandler): void {
    this.onDisconnectHandler = handler;
  }

  /**
   * Get connection state
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Get WebSocket ready state
   */
  getReadyState(): number | null {
    return this.ws?.readyState ?? null;
  }
}

/**
 * Render WebSocket stream to canvas
 */
export class CanvasStreamRenderer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private img: HTMLImageElement;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Failed to get 2D context from canvas');
    this.ctx = ctx;
    this.img = new Image();
  }

  /**
   * Render base64 frame to canvas
   */
  renderFrame(base64Data: string): void {
    this.img.onload = () => {
      // Resize canvas to match image
      if (this.canvas.width !== this.img.width || this.canvas.height !== this.img.height) {
        this.canvas.width = this.img.width;
        this.canvas.height = this.img.height;
      }
      
      // Draw image
      this.ctx.drawImage(this.img, 0, 0);
    };

    // Set image source
    this.img.src = `data:image/jpeg;base64,${base64Data}`;
  }

  /**
   * Clear canvas
   */
  clear(): void {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }
}
