import os
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional, Tuple
import numpy as np
import torch
from yacs.config import CfgNode

import cv2
from config.defaults import get_cfg_defaults
from config.config_tools import expand_relative_paths
from tools.util import parse_args
from tools import log
from mot.tracker import ByteTrackerIOU
from mot.tracklet import Tracklet
from detection.detection import Detection
from detection.load_detector import load_yolo
from reid.feature_extractor import FeatureExtractor
from reid.vehicle_reid.load_model import load_model_from_opts
from tools.preprocessing import create_extractor
from mtmc.mtmc_clustering import mtmc_clustering
from mtmc.cameras import CameraLayout


def build_extractor(cfg: CfgNode, device: torch.device):
    """Build ReID feature extractor with ONNX/TensorRT/PyTorch fallback."""
    if cfg.MOT.REID_TRT and os.path.exists(cfg.MOT.REID_TRT):
        log.info(f"Loading TensorRT ReID engine from {cfg.MOT.REID_TRT}")
        from reid.tensorrt_feature_extractor import TensorRTFeatureExtractor
        return TensorRTFeatureExtractor(cfg.MOT.REID_TRT)
    if cfg.MOT.REID_ONNX and os.path.exists(cfg.MOT.REID_ONNX):
        log.info(f"Loading ONNX ReID model from {cfg.MOT.REID_ONNX}")
        from reid.onnx_feature_extractor import ONNXFeatureExtractor
        return ONNXFeatureExtractor(cfg.MOT.REID_ONNX, use_gpu=device.type == "cuda")

    reid_model = load_model_from_opts(cfg.MOT.REID_MODEL_OPTS,
                                      ckpt=cfg.MOT.REID_MODEL_CKPT,
                                      remove_classifier=True)
    if cfg.MOT.REID_FP16:
        reid_model.half()
    reid_model.to(device)
    reid_model.eval()
    return create_extractor(FeatureExtractor, batch_size=cfg.MOT.REID_BATCHSIZE,
                             model=reid_model)


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None:
        return -1.0
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12
    return float(np.dot(a, b) / denom)


class VirtualClock:
    def __init__(self, interval: float, max_skew: int, stall_seconds: float, worker_names):
        self.interval = interval
        self.max_skew = max_skew
        self._cv = threading.Condition()
        self._tick = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._seen = {name: 0 for name in worker_names}
        now = time.time()
        self._last_ts = {name: now for name in worker_names}
        self.stall_seconds = stall_seconds

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        next_time = time.time() + self.interval
        while self._running:
            now = time.time()
            sleep_for = max(0.0, next_time - now)
            time.sleep(sleep_for)
            with self._cv:
                self._tick += 1
                self._cv.notify_all()
            next_time += self.interval

    def wait_for_tick(self, worker: str, last_seen: int) -> Optional[int]:
        with self._cv:
            while self._running:
                now = time.time()
                stale = [w for w, ts in self._last_ts.items() if now - ts > self.stall_seconds]
                for w in stale:
                    self._seen.pop(w, None)
                    self._last_ts.pop(w, None)

                target_tick = self._tick
                min_seen = min(self._seen.values()) if self._seen else target_tick
                allowed_tick = min_seen + self.max_skew
                next_tick = min(target_tick, allowed_tick)

                if next_tick > last_seen:
                    return next_tick

                self._cv.wait(timeout=0.5)
            return None

    def mark(self, worker: str, tick: int):
        with self._cv:
            if worker in self._seen:
                self._seen[worker] = tick
                self._last_ts[worker] = time.time()
            self._cv.notify_all()

    def retire(self, worker: str):
        with self._cv:
            self._seen.pop(worker, None)
            self._last_ts.pop(worker, None)
            self._cv.notify_all()

    def stop(self):
        self._running = False
        with self._cv:
            self._cv.notify_all()
        if self._thread:
            self._thread.join(timeout=2)


class LiveMTMCAggregator:
    def __init__(self, cams: Optional[CameraLayout], min_sim: float, linkage: str,
                 min_track_frames: int, cluster_interval: float):
        self.cams = cams
        self.min_sim = min_sim
        self.linkage = linkage
        self.min_track_frames = min_track_frames
        self.cluster_interval = cluster_interval
        self._lock = threading.Lock()
        self._tracks_by_cam: Dict[int, list] = {}
        self._gid_map: Dict[int, Dict[int, int]] = {}
        self._last_cluster_ts = 0.0

    def update(self, cam_idx: int, tracks: list) -> Dict[int, int]:
        """Update tracks for a camera and recompute global IDs.

        Returns a mapping from local track_id to global id for this camera.
        """
        with self._lock:
            self._tracks_by_cam[cam_idx] = list(tracks)
            self._recompute()
            return dict(self._gid_map.get(cam_idx, {}))

    def _recompute(self):
        now = time.time()
        if len(self._tracks_by_cam) == 0:
            return
        n_cams = self.cams.n_cams if self.cams else max(self._tracks_by_cam.keys()) + 1
        tracks_list = [self._tracks_by_cam.get(i, []) for i in range(n_cams)]

        total_tracks = sum(len(t) for t in tracks_list)
        if total_tracks == 0:
            # No active tracks anywhere; keep gid map empty
            self._gid_map = {i: {} for i in range(n_cams)}
            return

        if now - self._last_cluster_ts < self.cluster_interval:
            return

        # preserve original ids
        for ci, tlist in enumerate(tracks_list):
            for trk in tlist:
                if not hasattr(trk, "orig_id"):
                    trk.orig_id = trk.track_id
                trk.cam = ci
                if self.cams:
                    trk.global_start = trk.frames[0] / self.cams.fps[ci] / self.cams.scales[ci] + self.cams.offset[ci]
                    trk.global_end = trk.frames[-1] / self.cams.fps[ci] / self.cams.scales[ci] + self.cams.offset[ci]
                trk.idx = None

        # filter out very short tracks to reduce noise
        filtered_tracks = []
        for cam_tracks in tracks_list:
            filtered_tracks.append([t for t in cam_tracks if len(t.frames) >= self.min_track_frames])

        total_filtered = sum(len(t) for t in filtered_tracks)
        if total_filtered == 0:
            self._gid_map = {i: {} for i in range(n_cams)}
            return

        mtracks = mtmc_clustering(filtered_tracks, self.cams, min_sim=self.min_sim, linkage=self.linkage)

        gid_map: Dict[int, Dict[int, int]] = {i: {} for i in range(n_cams)}
        for mt in mtracks:
            gid = mt.id
            for trk in mt.tracks:
                orig = getattr(trk, "orig_id", trk.track_id)
                gid_map[trk.cam][orig] = gid

        # restore local ids
        for ci, tlist in enumerate(tracks_list):
            for trk in tlist:
                if hasattr(trk, "orig_id"):
                    trk.track_id = trk.orig_id

        self._gid_map = gid_map
        self._last_cluster_ts = now


class MJPEGBroadcaster:
    def __init__(self, port: int):
        self.port = port
        self.frames: Dict[str, Optional[bytes]] = {}
        self._lock = threading.Lock()
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()

    def update_frame(self, name: str, frame_bytes: bytes):
        with self._lock:
            self.frames[name] = frame_bytes

    def _handler_factory(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.lstrip("/") or "index"
                cam_name = path.split(".")[0]
                if cam_name == "index":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    body = "<html><body><h3>Live MJPEG streams</h3><ul>" + \
                        "".join([f'<li><a href="/{k}.mjpg">{k}</a></li>' for k in sorted(outer.frames.keys())]) + \
                        "</ul></body></html>"
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body.encode("utf-8"))
                    return

                boundary = "--frame"
                self.send_response(200)
                self.send_header("Age", "0")
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={boundary}")
                self.end_headers()

                try:
                    while outer._running.is_set():
                        with outer._lock:
                            buf = outer.frames.get(cam_name)
                        if buf is None:
                            time.sleep(0.05)
                            continue
                        self.wfile.write(boundary.encode() + b"\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(buf)}\r\n\r\n".encode())
                        self.wfile.write(buf)
                        self.wfile.write(b"\r\n")
                        time.sleep(0.001)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        return Handler

    def start(self):
        self._running.set()
        handler = self._handler_factory()
        self._server = ThreadingHTTPServer(("0.0.0.0", self.port), handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        log.info(f"MJPEG server started on port {self.port}")

    def stop(self):
        self._running.clear()
        if self._server:
            self._server.shutdown()
        if self._thread:
            self._thread.join(timeout=2)


class LiveMOTWorker(threading.Thread):
    def __init__(self, cam_idx: int, cam_cfg: CfgNode, base_cfg: CfgNode,
                 aggregator, broadcaster: MJPEGBroadcaster):
        super().__init__(daemon=True)
        self.cam_idx = cam_idx
        self.cam_cfg = cam_cfg
        self.base_cfg = base_cfg
        self.aggregator = aggregator
        self.broadcaster = broadcaster
        self.name = cam_cfg.get("name", f"cam_{cam_idx}")
        self.device = self._select_device(base_cfg)
        self.detector = load_yolo(cam_cfg.get("detector", base_cfg.MOT.DETECTOR)).to(self.device)
        self.tracked_classes = cam_cfg.get("tracked_classes", base_cfg.MOT.TRACKED_CLASSES)
        self.tracker = ByteTrackerIOU(frame_rate=30)
        self.extractor = build_extractor(base_cfg, self.device)
        self.video_path = cam_cfg.get("video")
        self.cap = cv2.VideoCapture(self.video_path)
        self.target_interval = 1.0 / float(base_cfg.LIVE.TARGET_FPS)
        self.min_confid = 0.05
        self.local_to_global: Dict[int, int] = {}
        self.gid_colors: Dict[int, Tuple[int, int, int]] = {}
        self.stop_event = threading.Event()
        self.frame_id = 0
        self.vclock = None
        self.bad_source = False
        if not self.video_path or not os.path.exists(self.video_path):
            log.error(f"Camera {self.name}: video source missing at {self.video_path}")
            self.bad_source = True
        elif not self.cap.isOpened():
            log.error(f"Camera {self.name}: cannot open video {self.video_path}")
            self.bad_source = True

    def _select_device(self, cfg: CfgNode) -> torch.device:
        if len(cfg.SYSTEM.GPU_IDS) == 0:
            return torch.device("cpu")
        gpu_id = min(map(int, cfg.SYSTEM.GPU_IDS))
        if gpu_id >= torch.cuda.device_count():
            log.error("GPU id %s not available, falling back to CPU", gpu_id)
            return torch.device("cpu")
        return torch.device(f"cuda:{gpu_id}")

    def run(self):
        log.info("Starting camera %s", self.name)
        last_ts = time.time()
        try:
            if self.bad_source:
                log.error("Camera %s exiting due to bad source", self.name)
                return
            while not self.stop_event.is_set():
                tick = self.vclock.wait_for_tick(self.name, self.frame_id)
                if tick is None:
                    break
                ret, frame = self.cap.read()
                if not ret:
                    if self.base_cfg.LIVE.LOOP_VIDEO:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    log.info("Camera %s ended", self.name)
                    break

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                detections, tracks = self._process_frame(frame, frame_rgb)
                annotated = self._annotate(frame, tracks)

                ok, buf = cv2.imencode('.jpg', annotated)
                if ok:
                    self.broadcaster.update_frame(self.name, buf.tobytes())

                # pace output
                elapsed = time.time() - last_ts
                sleep_for = max(0.0, self.target_interval - elapsed)
                time.sleep(sleep_for)
                last_ts = time.time()
                self.frame_id = tick
                self.vclock.mark(self.name, tick)
        finally:
            if self.vclock:
                self.vclock.retire(self.name)

    def _process_frame(self, frame_bgr, frame_rgb):
        res = self.detector(frame_bgr).xywh[0].cpu().numpy()
        boxes_raw = [t[:4] for t in res]
        scores_raw = [t[4] for t in res]
        classes_raw = [t[5] for t in res]

        filtered = []
        for bbox, score, cl in zip(boxes_raw, scores_raw, classes_raw):
            if score < self.min_confid or cl not in self.tracked_classes:
                continue
            filtered.append((bbox, score, cl))

        boxes_tlwh = [[int(x - w / 2), int(y - h / 2), w, h] for (x, y, w, h), _, _ in filtered]
        scores = [s for _, s, _ in filtered]
        classes = [c for _, _, c in filtered]

        features = self.extractor(frame_rgb, boxes_tlwh) if len(boxes_tlwh) > 0 else []
        detections = [Detection(bbox, score, clname, feature)
                      for bbox, score, clname, feature in zip(boxes_tlwh, scores, classes, features)]

        self.tracker.update(self.frame_id, detections, None, None)
        tracks = self.tracker.active_tracks
        for trk in tracks:
            trk.compute_mean_feature()
        # update global IDs via clustering aggregator
        gid_map = self.aggregator.update(self.cam_idx, tracks)
        for lid, gid in gid_map.items():
            self.local_to_global[lid] = gid
        return detections, tracks

    def _annotate(self, frame_bgr, tracks):
        vis = frame_bgr.copy()
        for trk in tracks:
            if len(trk.bboxes) == 0:
                continue
            x, y, w, h = map(int, trk.bboxes[-1])
            gid = self.local_to_global.get(trk.track_id, -1)
            color = self._color_for_gid(gid)
            cv2.rectangle(vis, (x, y), (x + w, y + h), color, 2)
            cv2.putText(vis, f"{gid}", (x, y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
        cv2.putText(vis, f"t={self.frame_id}", (8, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        return vis

    def _color_for_gid(self, gid: int) -> Tuple[int, int, int]:
        if gid not in self.gid_colors:
            # deterministic pseudo-random color per gid
            r = (37 * gid + 17) % 256
            g = (17 * gid + 101) % 256
            b = (97 * gid + 53) % 256
            self.gid_colors[gid] = (int(b), int(g), int(r))
        return self.gid_colors[gid]

    def stop(self):
        self.stop_event.set()
        self.cap.release()


def run_live(cfg: CfgNode):
    worker_names = [cam.get("name", f"cam_{idx}") for idx, cam in enumerate(cfg.EXPRESS.CAMERAS)]
    vclock = VirtualClock(interval=1.0 / float(cfg.LIVE.TARGET_FPS),
                          max_skew=cfg.LIVE.MAX_SKEW_TICKS,
                          stall_seconds=cfg.LIVE.STALL_SECONDS,
                          worker_names=worker_names)

    cams = CameraLayout(cfg.MTMC.CAMERA_LAYOUT) if cfg.MTMC.CAMERA_LAYOUT else None
    aggregator = LiveMTMCAggregator(cams,
                                    min_sim=cfg.MTMC.MIN_SIM,
                                    linkage=cfg.MTMC.LINKAGE,
                                    min_track_frames=cfg.LIVE.MIN_TRACK_FRAMES,
                                    cluster_interval=cfg.LIVE.CLUSTER_INTERVAL)

    broadcaster = MJPEGBroadcaster(port=cfg.LIVE.MJPEG_PORT)
    broadcaster.start()

    vclock.start()

    workers = []
    for idx, cam_info in enumerate(cfg.EXPRESS.CAMERAS):
        cam_cfg = dict(cam_info)
        worker = LiveMOTWorker(idx, cam_cfg, cfg, aggregator, broadcaster)
        worker.vclock = vclock
        workers.append(worker)
        broadcaster.update_frame(cam_cfg.get("name", f"cam_{idx}"), None)

    for w in workers:
        w.start()

    try:
        while any(w.is_alive() for w in workers):
            time.sleep(0.5)
    except KeyboardInterrupt:
        log.info("Stopping live MTMC...")
    finally:
        for w in workers:
            w.stop()
        vclock.stop()
        broadcaster.stop()


if __name__ == "__main__":
    args = parse_args("Run live MOT+MTMC with MJPEG streaming")
    cfg = get_cfg_defaults()
    if args.config:
        cfg.merge_from_file(os.path.join(cfg.SYSTEM.CFG_DIR, args.config))
    cfg = expand_relative_paths(cfg)
    cfg.freeze()

    if not os.path.exists(cfg.OUTPUT_DIR):
        os.makedirs(cfg.OUTPUT_DIR)

    log.log_init(os.path.join(cfg.OUTPUT_DIR, args.log_filename),
                 args.log_level, not args.no_log_stdout)
    run_live(cfg)
